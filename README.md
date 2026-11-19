# Metallbau-Quiz

Ein Lernspiel für Metallbauer in der Lehre. Wie ein Quiz: Zu jeder Frage gibt es vier Antworten, eine davon ist richtig. Nach jeder Antwort kommt eine kurze Erklärung.

- Die Fragen sind nach Themen geordnet (z. B. Werkstoffe, Schrauben, Geländer, Treppen).
- Jedes Thema läuft wie eine Lernkartei: Zuerst kommen alle Fragen einmal dran, dann nur noch die falschen, bis keine mehr übrig ist.
- Es gibt Punkte, Sterne und Ränge. Schnell sein bringt keine Punkte: lieber in Ruhe lesen.
- Der Fortschritt bleibt auf dem eigenen Gerät (im Browser gespeichert). Es gibt kein Konto, keine Werbung, und das Spiel braucht kein Internet.

## Spielen

Alles steckt in **einer Datei**: `metallbau-quiz.html`.

- **Am Computer:** Datei herunterladen und doppelt anklicken. Sie öffnet sich im Browser (Safari, Chrome, Firefox, Edge).
- **Auf dem Handy:** Die Datei im Browser öffnen, zum Beispiel über den Link der GitHub-Seite (falls eingerichtet).
- Mit der Tastatur geht es auch: Tasten 1 bis 4 wählen eine Antwort, die Eingabetaste geht weiter.

Der Fortschritt bleibt im Browser, in dem man spielt. Ein anderer Browser oder ein anderes Gerät beginnt wieder bei null.

## Eigene Fragen ergänzen

Die Fragen stehen in `metallbau-quiz.html` weiter unten bei `window.LERNSPIEL`. Die Datei kann man mit jedem Texteditor öffnen.

Der Aufbau ist so: **Gruppen** enthalten **Themen**, Themen enthalten **Fragen**.

```js
window.LERNSPIEL = {
 "titel": "Metallbau-Quiz",
 "kennung": "metallbau-quiz",
 "bilderOrdner": "",
 "gruppen": [
  {
   "name": "Werkstatt: Verbinden",
   "themen": [
    {
     "id": "schrauben",
     "name": "Schrauben und Gewinde",
     "fragen": [ ... ]
    }
   ]
  }
 ]
};
```

Eine Frage sieht so aus:

```js
{
 "id": "meine-01",
 "f": "Welches Werkzeug zieht eine Schraube mit dem richtigen Drehmoment an?",
 "r": "Drehmomentschlüssel",
 "x": ["Hammer", "Rohrzange", "Seitenschneider"],
 "e": "Der Drehmomentschlüssel zeigt an oder klickt, wenn die Kraft stimmt."
}
```

| Feld | Bedeutung |
|---|---|
| `id` | Feste Kennung der Frage. Jede Kennung darf nur einmal vorkommen. **Nie ändern**, sonst geht der Fortschritt für diese Frage verloren. |
| `f` | Die Frage |
| `r` | Die richtige Antwort |
| `x` | Genau drei falsche Antworten |
| `e` | Kurze Erklärung, die nach der Antwort erscheint |
| `b` | Bild (freiwillig): Name eines Bildes. Ein eigenes Bild legt man neben die HTML-Datei und schreibt hier seinen Dateinamen, z. B. `"b": "mein-bild.jpg"`. |
| `svg` | Eigene Skizze als SVG-Zeichnung (freiwillig) |

Ein Thema kann auch ein Bild haben (`"bild": "…"`), das in der Übersicht erscheint.

Tipps:

- Die Antworten etwa gleich lang machen, sonst verrät sich die richtige.
- Die vier Antworten müssen verschieden sein.
- Kurze Sätze schreiben. Ein Gedanke pro Frage.
- Nach dem Ändern die Datei im Browser neu laden und das Thema einmal durchspielen. Fehlt ein Komma oder eine Klammer, bleibt die Seite leer.

## Kahoots übernehmen

Das Script `tools/kahoot_import.py` holt die Fragen eines Kahoots und fügt sie als Thema ins Spiel ein. Es braucht nur Python 3.9 oder neuer.

```
python tools/kahoot_import.py "https://create.kahoot.it/share/…"
python tools/kahoot_import.py kahoot-links.txt
```

- In `kahoot-links.txt` stehen alle Kahoots aus der Kursarbeit in Teams. Neue Links einfach dazuschreiben und das Script nochmals laufen lassen.
- In der Linkliste legt eine Zeile `[Name]` die Gruppe für die Links darunter fest. Zeilen mit `#` sind Notizen.
- Mehrere Links auf einmal gehen auch. Ohne Link fragt das Script danach. Challenge-Links aus Teams gehen auch.
- Ohne Gruppe kommen neue Themen in die Gruppe «Kahoot». Eine andere Gruppe: `--gruppe "Name"`.
- Die Bilder kommen mit in die Datei. Das Spiel läuft weiter ohne Internet.
- Ein Kahoot, der schon drin ist, wird ersetzt, nicht doppelt eingefügt. `--aktualisieren` holt alle übernommenen Kahoots neu.
- `--vorschau` zeigt nur, was passieren würde.
- Hat eine Kahoot-Frage mehrere richtige Antworten, sind sie zusammen die Lösung (z. B. «ESG und TVG»).
- Freitext-, Pin-, Umfrage- und Puzzle-Fragen werden übersprungen, weil die falschen Antworten fehlen. Fragen, die nur mit einem Video gehen, auch. Das Script zeigt, welche.
- Die Bilder werden auf 600 px verkleinert. Trotzdem wird die Datei grösser (mit allen Kahoots aus Teams etwa 15 MB).
- Es geht nur mit Kahoots, die man ohne Anmeldung ansehen kann.

## Farben und Punkte ändern

- Farben: ganz oben in der Datei bei `:root`.
- Fragen pro Runde, Zeit pro Frage, Punkte und Ränge: oben im Skript bei «Einstellungen».

## Lizenz

- **Spiel und Fragen:** MIT-Lizenz (Datei `LICENSE`). Alle dürfen das Spiel benutzen, ändern und weitergeben, solange der Lizenztext dabei bleibt.
- **Bilder:** Für die Bilder gilt die MIT-Lizenz **nicht**. Ein Teil der Bilder stammt aus Adobe Stock. Diese Bilder sind nicht frei: Sie dürfen nicht aus dem Spiel herausgelöst und anders verwendet werden.
- **Übernommene Kahoots:** Fragen und Bilder gehören den Leuten, die den Kahoot gemacht haben. Ein Teil der Bilder stammt von Getty Images. Die MIT-Lizenz gilt dafür nicht.
