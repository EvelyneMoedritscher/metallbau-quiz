#!/usr/bin/env python3
"""
Kahoot-Import für das Metallbau-Quiz.

Holt die Fragen eines Kahoots und schreibt sie als Thema in metallbau-quiz.html.
Die Bilder werden mit eingebaut, damit das Spiel weiterhin ohne Internet läuft.

Aufruf (im Ordner metallbau-quiz):
  python tools/kahoot_import.py                     fragt nach den Links
  python tools/kahoot_import.py LINK [LINK ...]     einen oder mehrere Kahoot-Links übernehmen
  python tools/kahoot_import.py kahoot-links.txt    alle Links aus einer Textdatei übernehmen
  python tools/kahoot_import.py --aktualisieren     alle schon übernommenen Kahoots neu holen

In einer Textdatei setzt eine Zeile «[Gruppenname]» die Gruppe für die Links darunter.
Zeilen mit # am Anfang sind Notizen. Challenge-Links aus Teams gehen auch.

Optionen:
  --gruppe NAME   Gruppe für neue Themen (Standard: «Kahoot»)
  --vorschau      nur anzeigen, was passieren würde, nichts speichern

Ein Kahoot, der schon übernommen ist, wird ersetzt (nicht doppelt eingefügt).
Der Fortschritt bleibt erhalten, solange eine Frage gleich bleibt.

Was aus Kahoot-Fragen wird:
  Quiz, Wahr/Falsch    direkt übernommen
  mehrere richtige     die richtigen Antworten zusammen sind die Lösung («ESG und TVG»)
  Schieberegler        der richtige Wert und drei andere Werte als Auswahl
  Freitext, Umfrage,   übersprungen (dafür fehlen die falschen Antworten)
  Pin setzen, Puzzle …
  Frage nur mit Video  übersprungen (das Spiel zeigt keine Videos)

Braucht nur Python 3.9 oder neuer, keine Zusatzpakete.
"""

import argparse
import base64
import hashlib
import html
import itertools
import json
import math
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

QUIZ = Path(__file__).resolve().parent.parent / "metallbau-quiz.html"
KAHOOT_API = "https://create.kahoot.it/rest/kahoots/{}/card/?includeKahoot=true"
KAHOOT_SEITE = "https://create.kahoot.it/details/{}"
KAHOOT_CHALLENGE = "https://kahoot.it/rest/challenges/{}"
# Kahoot verkleinert die Bilder selbst. 600 px als JPG reichen fürs Handy und halten die Datei klein.
BILD_GROESSE = "width=600&quality=65&format=jpg"
STANDARD_GRUPPE = "Kahoot"
AGENT = "metallbau-quiz-kahoot-import/1.0"

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
CHALLENGE = re.compile(UUID.pattern + r"_\d+", re.I)
FRAGEN_BLOCK = re.compile(r"(window\.LERNSPIEL = )(\{.*?\n\})(;\n</script>)", re.S)
BILDER_BLOCK = re.compile(r"(window\.LERNSPIEL_BILDER = )(\{.*?\n\})(;\n</script>)", re.S)
BILD_ENDUNG = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
WAHR_FALSCH = {"true": "Wahr", "false": "Falsch"}
TYP_NAMEN = {
    "open_ended": "Freitext-Antwort",
    "word_cloud": "Wortwolke",
    "survey": "Umfrage",
    "poll": "Umfrage",
    "content": "Folie ohne Frage",
    "jumble": "Puzzle (Reihenfolge)",
    "drop_pin": "Pin setzen",
    "pin_it": "Pin setzen",
    "brainstorm": "Brainstorming",
    "scale": "Skala",
    "nps": "Bewertung",
    "feedback": "Rückmeldung",
}


class Fehler(Exception):
    pass


# ---------------------------------------------------------------- Links lesen

def kahoot_ids(eingaben, gruppe):
    """Findet die Kahoots in Links, Textdateien oder eingefügtem Text.

    Gibt [(kennung, gruppe)] zurück. In einer Textdatei setzt eine Zeile «[Name]»
    die Gruppe für die Links darunter. Zeilen, die mit # beginnen, sind Notizen.
    """
    zeilen = []
    for e in eingaben:
        try:
            ist_datei = "://" not in e and Path(e).is_file()
        except (OSError, ValueError):
            ist_datei = False
        zeilen += Path(e).read_text(encoding="utf-8-sig", errors="replace").splitlines() if ist_datei else [e]
    ergebnis, gesehen = [], set()
    for zeile in zeilen:
        zeile = zeile.strip()
        kopf = re.fullmatch(r"\[(.+)\]", zeile)
        if kopf:
            gruppe = kopf.group(1).strip()
            continue
        if zeile.startswith("#"):
            continue
        for wort in zeile.split():
            kennung = kennung_aus_link(wort)
            if kennung and kennung not in gesehen:
                gesehen.add(kennung)
                ergebnis.append((kennung, gruppe))
    return ergebnis


def kennung_aus_link(wort):
    wort = wort.strip("<>\"'()[],;")
    teile = urllib.parse.urlsplit(wort)
    # Challenge-Links (kahoot.it/challenge/…) zeigen auf ein Spiel, nicht auf den Kahoot selbst.
    challenge = CHALLENGE.search(wort)
    if challenge or "/challenge" in teile.path.lower():
        if challenge:
            return challenge_aufloesen(challenge.group(0))
        print(f"Achtung: «{wort}» ist ein Challenge-Link ohne Kennung. Nimm den ganzen Link aus Teams.")
        return None
    # Die Kennung steht im Pfad. Im Rest (z. B. ?classId=…) stehen andere Kennungen.
    treffer = UUID.search(teile.path)
    if not treffer:
        for name, wert in urllib.parse.parse_qsl(teile.query):
            if "quiz" in name.lower() and UUID.fullmatch(wert):
                treffer = UUID.fullmatch(wert)
                break
    if treffer:
        return treffer.group(0).lower()
    if "kahoot" in wort.lower():
        print(f"Achtung: In «{wort}» steckt kein Kahoot, das ich lesen kann. "
              "Nimm den Link aus «Teilen» oder aus der Adresszeile von create.kahoot.it.")
    return None


def challenge_aufloesen(challenge):
    """Sucht zu einer Challenge den Kahoot, der dahinter steckt."""
    try:
        daten, _ = herunterladen(KAHOOT_CHALLENGE.format(challenge))
        quiz = json.loads(daten).get("quizId") or ""
    except (urllib.error.URLError, OSError, ValueError):
        quiz = ""
    if UUID.fullmatch(quiz):
        return quiz.lower()
    print(f"Achtung: Die Challenge {challenge} lässt sich nicht öffnen (abgelaufen oder nicht öffentlich).")
    return None


# ---------------------------------------------------------------- Kahoot holen

def herunterladen(url):
    anfrage = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(anfrage, timeout=30) as antwort:
        return antwort.read(), antwort.headers.get_content_type()


def kahoot_holen(kennung):
    try:
        daten, _ = herunterladen(KAHOOT_API.format(kennung))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise Fehler("nicht gefunden oder nicht öffentlich. "
                         "Nur Kahoots, die man ohne Anmeldung ansehen kann, lassen sich übernehmen.")
        raise Fehler(f"Kahoot antwortet mit Fehler {e.code}.")
    except urllib.error.URLError as e:
        raise Fehler(f"keine Verbindung zu Kahoot ({e.reason}).")
    try:
        return json.loads(daten)["kahoot"]
    except (ValueError, KeyError):
        raise Fehler("Kahoot hat unerwartete Daten geschickt.")


def bild_holen(url, bilder):
    """Lädt ein Bild, legt es in die Bilder des Spiels und gibt seinen Namen zurück."""
    teile = urllib.parse.urlsplit(url)
    stamm = "kahoot_" + re.sub(r"[^0-9A-Za-z_-]", "", teile.path.rsplit("/", 1)[-1].removesuffix("_opt"))
    for name in bilder:                      # schon da (z. B. vom letzten Import)
        if name.rsplit(".", 1)[0] == stamm:
            return name
    if teile.hostname and teile.hostname.endswith("kahoot.it"):
        url += ("&" if teile.query else "?") + BILD_GROESSE
    try:
        daten, art = herunterladen(url)
    except (urllib.error.URLError, OSError) as e:
        print(f"    Bild nicht geladen ({e}), Frage bleibt ohne Bild")
        return None
    if art not in BILD_ENDUNG:
        print(f"    Bild hat ein unbekanntes Format ({art}), Frage bleibt ohne Bild")
        return None
    name = f"{stamm}.{BILD_ENDUNG[art]}"
    bilder[name] = f"data:{art};base64," + base64.b64encode(daten).decode("ascii")
    return name


# ---------------------------------------------------------------- Fragen umwandeln

def reiner_text(s):
    """Kahoot-Text ohne HTML (fett, Zeilenumbrüche, &nbsp; …)."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def aufzaehlen(teile):
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + " und " + teile[-1]


def ohne_doppelte(liste, ausser=()):
    gesehen, ergebnis = {a.casefold() for a in ausser}, []
    for a in liste:
        if a and a.casefold() not in gesehen:
            gesehen.add(a.casefold())
            ergebnis.append(a)
    return ergebnis


def stellen(*zahlen):
    return max(max(0, -Decimal(repr(float(z))).normalize().as_tuple().exponent) for z in zahlen)


def schieberegler(bereich):
    """Macht aus einem Schieberegler eine Auswahl: richtiger Wert und drei Werte daneben."""
    von, bis, richtig = bereich["start"], bereich["end"], bereich["correct"]
    schritt = bereich.get("step") or 1
    toleranz = bereich.get("tolerance") or 0
    n = stellen(schritt, richtig)
    zeigen = lambda w: f"{w:.{n}f}".replace(".", ",")
    abstand = max(schritt, (bis - von) / 6, toleranz + schritt)
    abstand = math.ceil(abstand / schritt - 1e-9) * schritt
    falsch = []
    for k in range(1, 100):
        for w in (richtig - k * abstand, richtig + k * abstand):
            if von - 1e-9 <= w <= bis + 1e-9 and abs(w - richtig) > toleranz:
                falsch.append(zeigen(w))
        if len(falsch) >= 3 or richtig - k * abstand < von and richtig + k * abstand > bis:
            break
    return zeigen(richtig), ohne_doppelte(falsch, [zeigen(richtig)])[:3], ""


def auswahl(frage):
    """Gibt (richtig, falsch, erklärung) zurück oder wirft Fehler mit dem Grund."""
    wahl = frage.get("choices") or []
    if any(c.get("image") and not reiner_text(c.get("answer")) for c in wahl):
        raise Fehler("Antworten sind Bilder")

    # Wahr/Falsch speichert Kahoot auf Englisch («True»/«False»), zeigt es aber auf Deutsch.
    wahr_falsch = {reiner_text(c.get("answer")).lower() for c in wahl} <= set(WAHR_FALSCH)

    def text(c):
        t = reiner_text(c.get("answer"))
        return WAHR_FALSCH.get(t.lower(), t) if wahr_falsch else t

    richtige = ohne_doppelte([text(c) for c in wahl if c.get("correct")])
    alle = ohne_doppelte([text(c) for c in wahl])
    if not richtige:
        raise Fehler("keine richtige Antwort markiert")
    if len(richtige) > 1:
        # Im Spiel gibt es nur eine Lösung: die richtigen Antworten zusammen.
        # Falsch sind die anderen Kombinationen gleicher Grösse.
        loesung = aufzaehlen(richtige)
        kombis = [aufzaehlen(list(k)) for k in itertools.combinations(alle, len(richtige))]
        falsch = [k for k in kombis if k != loesung][:3]
        return loesung, falsch, "Im Kahoot waren mehrere Antworten richtig."
    falsch = ohne_doppelte([a for a in alle if a not in richtige], richtige)
    return richtige[0], falsch[:3], ""


def frage_umwandeln(frage):
    typ = frage.get("type")
    if typ in ("quiz", "true_false", "multiple_select_quiz"):
        richtig, falsch, erklaerung = auswahl(frage)
    elif typ == "slider" and frage.get("choiceRange"):
        richtig, falsch, erklaerung = schieberegler(frage["choiceRange"])
    else:
        raise Fehler(TYP_NAMEN.get(typ, f"Fragetyp «{typ}»") + ", geht nicht als Auswahl")
    if not falsch:
        raise Fehler("keine falschen Antworten")
    video = frage.get("video") or {}
    if not frage.get("image") and (video.get("id") or video.get("fullUrl")):
        raise Fehler("braucht ein Video")
    return richtig, falsch, erklaerung


def frage_kennung(kahoot, text, richtig, bild_url, vergeben):
    """Feste Kennung: bleibt gleich, solange Frage, Lösung und Bild gleich bleiben."""
    pruef = hashlib.sha1(f"{text}|{richtig}|{bild_url or ''}".encode("utf-8")).hexdigest()[:6]
    basis = f"k{kahoot[:6]}-{pruef}"
    kennung, n = basis, 2
    while kennung in vergeben:
        kennung, n = f"{basis}-{n}", n + 1
    vergeben.add(kennung)
    return kennung


def thema_bauen(kennung, kahoot, bilder, vergeben, vorschau):
    titel = reiner_text(kahoot.get("title")) or "Kahoot"
    print(f"\n{titel}  ({KAHOOT_SEITE.format(kennung)})")
    fragen, uebersprungen, bildzahl = [], [], 0
    for nr, frage in enumerate(kahoot.get("questions") or [], 1):
        text = reiner_text(frage.get("question"))
        try:
            if not text:
                raise Fehler("Frage ohne Text")
            richtig, falsch, erklaerung = frage_umwandeln(frage)
        except Fehler as grund:
            uebersprungen.append(f"{nr:2}. {text[:60] or '(ohne Text)'}  → {grund}")
            continue
        neu = {"id": frage_kennung(kennung, text, richtig, frage.get("image"), vergeben),
               "f": text, "r": richtig, "x": falsch}
        if erklaerung:
            neu["e"] = erklaerung
        if frage.get("image"):
            bildzahl += 1
            if not vorschau:
                name = bild_holen(frage["image"], bilder)
                if name:
                    neu["b"] = name
        fragen.append(neu)

    print(f"  übernommen: {len(fragen)} Fragen, davon {bildzahl} mit Bild")
    if uebersprungen:
        print(f"  übersprungen: {len(uebersprungen)}")
        for zeile in uebersprungen:
            print("    " + zeile)
    if not fragen:
        raise Fehler("keine Frage liess sich übernehmen.")

    thema = {"id": f"kahoot-{kennung[:8]}", "name": titel}
    if kahoot.get("cover") and not vorschau:
        name = bild_holen(kahoot["cover"], bilder)
        if name:
            thema["bild"] = name
    thema["kahoot"] = KAHOOT_SEITE.format(kennung)
    thema["fragen"] = fragen
    return thema


# ---------------------------------------------------------------- Quiz-Datei

def quiz_lesen():
    roh = QUIZ.read_bytes().decode("utf-8")
    crlf = "\r\n" in roh
    seite = roh.replace("\r\n", "\n")
    f, b = FRAGEN_BLOCK.search(seite), BILDER_BLOCK.search(seite)
    if not f or not b:
        raise Fehler(f"In {QUIZ.name} finde ich «window.LERNSPIEL» oder «window.LERNSPIEL_BILDER» nicht.")
    return seite, crlf, json.loads(f.group(2)), json.loads(b.group(2))


def als_skript(wert, einzug):
    text = json.dumps(wert, indent=einzug, ensure_ascii=False)
    # Ein «</script» im Text würde den Skriptblock beenden.
    return re.sub(r"</(script)", r"<\\/\1", text, flags=re.I).replace("<!--", "\\u003c!--")


def quiz_schreiben(seite, crlf, daten, bilder):
    seite = FRAGEN_BLOCK.sub(lambda m: m.group(1) + als_skript(daten, 1) + m.group(3), seite, count=1)
    seite = BILDER_BLOCK.sub(lambda m: m.group(1) + als_skript(bilder, 2) + m.group(3), seite, count=1)
    if crlf:
        seite = seite.replace("\n", "\r\n")
    fd, tmp = tempfile.mkstemp(dir=QUIZ.parent, prefix=".kahoot-", suffix=".html")
    try:
        with os.fdopen(fd, "wb") as datei:
            datei.write(seite.encode("utf-8"))
        os.replace(tmp, QUIZ)
    except BaseException:
        os.unlink(tmp)
        raise


def thema_einsetzen(daten, thema, gruppenname):
    for gruppe in daten["gruppen"]:
        for i, t in enumerate(gruppe["themen"]):
            if t["id"] == thema["id"]:
                gruppe["themen"][i] = thema
                return f"Thema ersetzt (Gruppe «{gruppe['name']}»)"
    for gruppe in daten["gruppen"]:
        if gruppe["name"] == gruppenname:
            gruppe["themen"].append(thema)
            return f"neues Thema in Gruppe «{gruppenname}»"
    daten["gruppen"].append({"name": gruppenname, "themen": [thema]})
    return f"neues Thema in neuer Gruppe «{gruppenname}»"


def alte_kahoot_bilder_entfernen(daten, bilder):
    gebraucht = set()
    for gruppe in daten["gruppen"]:
        for t in gruppe["themen"]:
            gebraucht.add(t.get("bild"))
            gebraucht.update(f.get("b") for f in t.get("fragen", []))
    for name in [n for n in bilder if n.startswith("kahoot_") and n not in gebraucht]:
        del bilder[name]


def alle_kennungen(daten, ausser_thema):
    return {f["id"] for g in daten["gruppen"] for t in g["themen"] if t["id"] != ausser_thema
            for f in t.get("fragen", [])}


# ---------------------------------------------------------------- Ablauf

def main():
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="replace")
        except AttributeError:
            pass
    p = argparse.ArgumentParser(description="Kahoots ins Metallbau-Quiz übernehmen.")
    p.add_argument("links", nargs="*", help="Kahoot-Links oder eine Textdatei mit Links")
    p.add_argument("--gruppe", default=STANDARD_GRUPPE, help=f"Gruppe für neue Themen (Standard: {STANDARD_GRUPPE})")
    p.add_argument("--aktualisieren", action="store_true", help="alle schon übernommenen Kahoots neu holen")
    p.add_argument("--vorschau", action="store_true", help="nur anzeigen, nichts speichern")
    args = p.parse_args()

    seite, crlf, daten, bilder = quiz_lesen()

    eingaben = list(args.links)
    if args.aktualisieren:
        eingaben += [t["kahoot"] for g in daten["gruppen"] for t in g["themen"] if t.get("kahoot")]
    if not eingaben:
        print("Kahoot-Links einfügen (einen pro Zeile). Leere Zeile = fertig.")
        while True:
            try:
                zeile = input("> ").strip()
            except EOFError:
                break
            if not zeile:
                break
            eingaben.append(zeile)
    ids = kahoot_ids(eingaben, args.gruppe)
    if not ids:
        print("Kein Kahoot-Link gefunden. Nichts geändert.")
        return 1

    geaendert, fehler = 0, 0
    for kennung, gruppe in ids:
        try:
            kahoot = kahoot_holen(kennung)
            vergeben = alle_kennungen(daten, f"kahoot-{kennung[:8]}")
            thema = thema_bauen(kennung, kahoot, bilder, vergeben, args.vorschau)
            print("  → " + thema_einsetzen(daten, thema, gruppe))
            geaendert += 1
        except Fehler as grund:
            print(f"\nKahoot {kennung}: {grund}")
            fehler += 1

    if args.vorschau:
        print("\nVorschau: nichts gespeichert.")
    elif geaendert:
        alte_kahoot_bilder_entfernen(daten, bilder)
        quiz_schreiben(seite, crlf, daten, dict(sorted(bilder.items())))
        print(f"\nGespeichert in {QUIZ.name}. Seite im Browser neu laden und ein Thema anspielen.")
    return 1 if fehler else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fehler as grund:
        print(grund)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
