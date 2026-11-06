from datetime import datetime, time, timedelta, timezone

from custom_components.pilotage_ballon.model import Appris, Detection, fenetre_hc, planifier

TZ = timezone(timedelta(hours=1))


def test_fenetre_hc():
    d, f, dedans = fenetre_hc(datetime(2026, 11, 6, 23, 0, tzinfo=TZ), time(22), time(6))
    assert dedans and d.day == 6 and f.day == 7
    d, f, dedans = fenetre_hc(datetime(2026, 11, 7, 2, 0, tzinfo=TZ), time(22), time(6))
    assert dedans and d.day == 6 and f.day == 7
    d, f, dedans = fenetre_hc(datetime(2026, 11, 7, 12, 0, tzinfo=TZ), time(22), time(6))
    assert not dedans and d.day == 7 and d.hour == 22 and f.day == 8


def test_apprentissage_p80():
    a = Appris()
    assert not a.fiable() and a.duree(240) == 240
    for d in (150, 160, 170, 180, 190, 200, 300):
        a.ajouter(d, 4000)
    assert a.fiable() and a.duree(240) == 200               # 80e centile, pas la moyenne
    a.ajouter(5, 100)
    a.ajouter(900, 100)
    assert len(a.durees) == 7                               # trop court / trop long : ignorés


def test_plan_serre_si_la_duree_depasse_la_nuit():
    a = Appris()
    for _ in range(5):
        a.ajouter(400, 9000)
    p = planifier(datetime(2026, 11, 6, 20, 0, tzinfo=TZ), time(22), time(6), 30, 1.15, 240, a, None, False)
    assert p.serre and p.debut.hour == 22


def test_nuit_deja_chaude():
    a = Appris()
    maintenant = datetime(2026, 11, 7, 3, 0, tzinfo=TZ)
    p = planifier(maintenant, time(22), time(6), 30, 1.15, 240, a, datetime(2026, 11, 7, 1, 10, tzinfo=TZ), False)
    assert not p.besoin and "01:10" in p.raison


def test_detection_anti_rebond():
    d = Detection()
    assert d.pas(0, 2000, 200, 50, 120, 300)[0] is None
    assert d.pas(60, 10, 200, 50, 120, 300)[0] is None       # pic isolé : pas de chauffe
    ev = [d.pas(t, 2000, 200, 50, 120, 300) for t in (100, 160, 230)]
    assert ev[-1][0] == "debut" and ev[-1][1] == 100
    assert d.pas(1000, 10, 200, 50, 120, 300)[0] is None
    assert d.pas(1100, 2000, 200, 50, 120, 300)[0] is None   # reprise : on ne termine pas
    assert d.pas(2000, 0, 200, 50, 120, 300)[0] is None
    ev = d.pas(2400, 0, 200, 50, 120, 300)
    assert ev == ("fin", 2000)
