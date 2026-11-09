from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import classements
from django.forms import ValidationError

from .forms import parse_chrono
from .models import Boucle, Course, Participant


class SerieTests(TestCase):
    def test_series(self):
        self.assertEqual(classements.serie_max([]), 0)
        self.assertEqual(classements.serie_max([4]), 1)
        self.assertEqual(classements.serie_max([1, 2, 3, 5, 6, 9]), 3)
        self.assertEqual(classements.serie_max([9, 2, 8, 7, 10]), 4)


class ChronoTests(TestCase):
    def test_formats(self):
        self.assertEqual(parse_chrono("52"), timedelta(minutes=52))
        self.assertEqual(parse_chrono("52:30"), timedelta(minutes=52, seconds=30))
        self.assertEqual(parse_chrono("1:10:00"), timedelta(hours=1, minutes=10))
        self.assertEqual(parse_chrono("1h20"), timedelta(hours=1, minutes=20))
        self.assertEqual(parse_chrono("75"), timedelta(minutes=75))  # incohérent mais accepté

    def test_invalide(self):
        with self.assertRaises(ValidationError):
            parse_chrono("abc")


class CalendrierTests(TestCase):
    def setUp(self):
        self.course = Course.get()
        self.t0 = timezone.now().replace(microsecond=0)
        self.course.premier_depart = self.t0
        self.course.tolerance_minutes = 5
        self.course.save()

    def test_ouverture(self):
        c, t0 = self.course, self.t0
        self.assertEqual(c.nb_boucles_ouvertes(t0 - timedelta(minutes=6)), 0)
        self.assertEqual(c.nb_boucles_ouvertes(t0 - timedelta(minutes=4)), 1)  # tolérance
        self.assertEqual(c.nb_boucles_ouvertes(t0 + timedelta(minutes=50)), 1)
        self.assertEqual(c.nb_boucles_ouvertes(t0 + timedelta(minutes=56)), 2)
        self.assertEqual(c.nb_boucles_ouvertes(t0 + timedelta(days=5)), c.nb_boucles_max)
        self.assertEqual(c.boucle_en_cours(t0 + timedelta(hours=2, minutes=1)), 3)


class ParticipantTests(TestCase):
    def test_pseudo_unique_insensible_a_la_casse(self):
        Participant.objects.create(prenom="A", nom="B", pseudo="Lulu", genre="H")
        with self.assertRaises(IntegrityError):
            Participant.objects.create(prenom="C", nom="D", pseudo="lulu", genre="F")


class ParcoursCoureurTests(TestCase):
    def setUp(self):
        course = Course.get()
        course.premier_depart = timezone.now() - timedelta(hours=2, minutes=10)  # boucle 3 en cours
        course.save()

    def inscrire(self, pseudo):
        self.client.post(reverse("course:inscription"),
                         {"prenom": "X", "nom": "Y", "pseudo": pseudo, "genre": "F"})
        return Participant.objects.get(pseudo=pseudo)

    def test_cocher_puis_decocher(self):
        p = self.inscrire("zoe")
        url = reverse("course:basculer_boucle", args=[p.pk, 2])
        self.client.post(url)
        self.assertTrue(p.boucles.filter(numero=2).exists())
        self.client.post(url)
        self.assertFalse(p.boucles.filter(numero=2).exists())

    def test_boucle_future_refusee(self):
        p = self.inscrire("zoe")
        r = self.client.post(reverse("course:basculer_boucle", args=[p.pk, 5]))
        self.assertEqual(r.status_code, 400)

    def test_chrono_coche_la_boucle(self):
        p = self.inscrire("zoe")
        self.client.post(reverse("course:saisir_chrono", args=[p.pk, 1]), {"chrono": "48:12"})
        self.assertEqual(p.boucles.get(numero=1).chrono, timedelta(minutes=48, seconds=12))

    def test_compte_d_un_autre_interdit(self):
        autre = Participant.objects.create(prenom="A", nom="B", pseudo="autre", genre="H")
        self.inscrire("zoe")
        r = self.client.post(reverse("course:basculer_boucle", args=[autre.pk, 1]))
        self.assertEqual(r.status_code, 403)

    def test_multi_comptes_et_bascule(self):
        a = self.inscrire("a")
        b = self.inscrire("b")
        self.assertEqual(self.client.get(reverse("course:moi")).context["participant"], b)
        self.client.post(reverse("course:basculer_compte", args=["suivant"]))
        self.assertEqual(self.client.get(reverse("course:moi")).context["participant"], a)

    def test_expiration_24h(self):
        self.inscrire("zoe")
        s = self.client.session
        s["comptes"][0][1] = (timezone.now() - timedelta(hours=25)).isoformat()
        s.save()
        self.assertRedirects(self.client.get(reverse("course:moi")), reverse("course:connexion"))

    def test_gestion_peut_tout_modifier(self):
        p = Participant.objects.create(prenom="A", nom="B", pseudo="p", genre="H")
        User.objects.create_user("orga", password="x", is_staff=True)
        self.client.login(username="orga", password="x")
        self.client.post(reverse("course:basculer_boucle", args=[p.pk, 10]))
        self.assertEqual(p.boucles.get().saisie_par, Boucle.Source.GESTION)


class PagesTests(TestCase):
    def test_pages_publiques(self):
        p = Participant.objects.create(prenom="A", nom="B", pseudo="p", genre="H")
        for url in [reverse("course:accueil"), reverse("course:resume_course"), reverse("course:coureur", args=["P"])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for filtres in ["?genre=E", "?critere=serie&genre=F", "?critere=chrono", "?critere=nimportequoi"]:
            self.assertEqual(self.client.get(reverse("course:accueil") + filtres).status_code, 200, filtres)
        self.assertRedirects(self.client.get(reverse("course:bilan")), reverse("course:accueil"))
        self.assertIsNotNone(p)


class ClassementTests(TestCase):
    def setUp(self):
        course = Course.get()
        course.premier_depart = timezone.now() - timedelta(hours=5, minutes=10)
        course.save()
        self.course = course

    def coureur(self, pseudo, numeros, genre="F", chrono=None):
        p = Participant.objects.create(prenom="A", nom="B", pseudo=pseudo, genre=genre)
        for n in numeros:
            Boucle.objects.create(participant=p, numero=n, chrono=chrono)
        return p

    def test_ex_aequo_sans_second_critere(self):
        self.coureur("a", [1, 2, 3])          # série 3
        self.coureur("b", [1, 3, 5])          # série 1, même nb de boucles
        self.coureur("c", [1])
        rangs = {s.participant.pseudo: s.rang for s in classements.classement(classements.toutes_les_stats())}
        self.assertEqual(rangs, {"a": 1, "b": 1, "c": 3})

    def test_classement_par_serie_et_par_chrono(self):
        self.coureur("a", [1, 2, 3], chrono=timedelta(minutes=50))  # série 3
        self.coureur("b", [1, 3, 5], chrono=timedelta(minutes=42))  # série 1
        self.coureur("c", [4, 5, 6])                                 # série 3, pas de chrono
        self.coureur("d", [])                                        # jamais parti
        stats = classements.toutes_les_stats()
        serie = [(s.participant.pseudo, s.rang) for s in classements.classement(stats, "serie")]
        self.assertEqual(serie, [("a", 1), ("c", 1), ("b", 3)])
        chrono = [(s.participant.pseudo, s.rang) for s in classements.classement(stats, "chrono")]
        self.assertEqual(chrono, [("b", 1), ("a", 2)])

    def test_resume_course(self):
        self.coureur("a", [1, 2])
        self.coureur("b", [])
        r = classements.resume_course()
        self.assertEqual((r["participants"], r["boucles"], r["max_par_boucle"]), (2, 2, 1))

    def test_coureurs_par_boucle(self):
        self.coureur("a", [1, 2])
        self.coureur("b", [2])
        par_boucle = classements.coureurs_par_boucle(self.course, classements.toutes_les_stats())
        self.assertEqual(par_boucle[:3], [(1, 1), (2, 2), (3, 0)])


class ClotureEtGestionTests(TestCase):
    def setUp(self):
        self.course = Course.get()
        self.course.premier_depart = timezone.now() - timedelta(hours=2, minutes=10)
        self.course.save()
        self.p = Participant.objects.create(prenom="Zoé", nom="Durand", pseudo="zoe", genre="F")
        User.objects.create_user("orga", password="x", is_staff=True)

    def test_cloture_bloque_le_coureur_pas_la_gestion(self):
        self.client.post(reverse("course:connexion"), {"pseudo": "zoe"})
        self.course.cloturee = True
        self.course.save()
        r = self.client.post(reverse("course:basculer_boucle", args=[self.p.pk, 1]))
        self.assertEqual(r.status_code, 400)
        self.client.login(username="orga", password="x")
        self.client.post(reverse("course:basculer_boucle", args=[self.p.pk, 1]))
        self.assertTrue(self.p.boucles.filter(numero=1).exists())

    def test_plus_un_reversible(self):
        self.client.login(username="orga", password="x")
        url = reverse("course:gestion_plus_un", args=[self.p.pk])
        self.client.post(url)
        self.assertEqual(list(self.p.boucles.values_list("numero", flat=True)), [3])
        r = self.client.post(url)
        self.assertFalse(self.p.boucles.exists())
        self.assertContains(r, "<td>1</td>")  # le rang reste affiché

    def test_export_csv(self):
        Boucle.objects.create(participant=self.p, numero=1, chrono=timedelta(minutes=45))
        Boucle.objects.create(participant=self.p, numero=2)
        self.client.login(username="orga", password="x")
        contenu = self.client.get(reverse("course:gestion_export")).content.decode("utf-8-sig")
        entete, ligne = contenu.splitlines()[:2]
        self.assertTrue(entete.startswith("Rang;Pseudo;Prénom"))
        self.assertTrue(ligne.startswith("1;zoe;Zoé;Durand;Femme;2;"))
        self.assertIn(";45:00;x;", ligne)

    def test_fiche_publique_sans_boucle_future(self):
        r = self.client.get(reverse("course:coureur", args=["zoe"]))
        self.assertEqual([l.numero for l in r.context["lignes"]], [3, 2, 1])

    def test_recherche_garde_le_rang(self):
        autre = Participant.objects.create(prenom="A", nom="B", pseudo="autre", genre="H")
        Boucle.objects.create(participant=autre, numero=1)
        Boucle.objects.create(participant=self.p, numero=1)
        Boucle.objects.create(participant=autre, numero=2)
        r = self.client.get(reverse("course:accueil") + "?q=ZO", HTTP_HX_REQUEST="true")
        stats = r.context["stats"]
        self.assertEqual([(s.participant.pseudo, s.rang) for s in stats], [("zoe", 2)])  # autre : 2 boucles, zoe : 1

    def test_pages_ecran_horloge_carnet(self):
        for url in [reverse("course:ecran"), reverse("course:horloge"), reverse("course:carnet", args=[self.p.pk])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)


class ConnexionOrganisateurTests(TestCase):
    def test_connexion_hors_admin(self):
        User.objects.create_user("orga", password="motdepasse", is_staff=True)
        r = self.client.get(reverse("course:gestion_liste"))
        self.assertRedirects(r, reverse("course:gestion_connexion") + "?next=" + reverse("course:gestion_liste"))
        r = self.client.post(reverse("course:gestion_connexion"), {"username": "orga", "password": "motdepasse"})
        self.assertRedirects(r, reverse("course:gestion_liste"))

    def test_compte_non_staff_refuse(self):
        User.objects.create_user("lambda", password="motdepasse")
        r = self.client.post(reverse("course:gestion_connexion"), {"username": "lambda", "password": "motdepasse"})
        self.assertContains(r, "pas accès à la gestion")

    def test_deconnexion(self):
        User.objects.create_user("orga", password="motdepasse", is_staff=True)
        self.client.login(username="orga", password="motdepasse")
        self.client.post(reverse("course:gestion_deconnexion"))
        self.assertEqual(self.client.get(reverse("course:gestion_liste")).status_code, 302)


class GabaritsTests(TestCase):
    def test_aucun_commentaire_visible(self):
        """Un {# … #} sur plusieurs lignes s'afficherait tel quel dans la page."""
        p = Participant.objects.create(prenom="A", nom="B", pseudo="p", genre="H")
        self.client.post(reverse("course:connexion"), {"pseudo": "p"})
        for url in [reverse("course:accueil"), reverse("course:moi"), reverse("course:ecran"),
                    reverse("course:carnet", args=[p.pk]), reverse("course:coureur", args=["p"])]:
            self.assertNotContains(self.client.get(url), "{#", msg_prefix=url)


class EcranTests(TestCase):
    def test_trois_criteres_et_reglage(self):
        course = Course.get()
        course.premier_depart = timezone.now() - timedelta(hours=1, minutes=10)
        course.ecran_bascule_minutes = 5
        course.save()
        p = Participant.objects.create(prenom="A", nom="B", pseudo="p", genre="E")
        Boucle.objects.create(participant=p, numero=1, chrono=timedelta(minutes=41))
        for critere, attendu in [("boucles", "boucle"), ("serie", "affilée"), ("chrono", "41:00")]:
            r = self.client.get(reverse("course:ecran") + f"?critere={critere}", HTTP_HX_REQUEST="true")
            self.assertContains(r, attendu)
            self.assertContains(r, 'data-bascule="5"')
