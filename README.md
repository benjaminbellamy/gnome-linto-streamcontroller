# LinTO plugin for Stream Controller

<p align="center">
  <img src="store/Thumbnail.png" width="640" alt="LinTO plugin for Stream Controller">
</p>

A [StreamController](https://github.com/StreamController/StreamController) plugin
to control the [gnome-linto](https://github.com/benjaminbellamy/gnome-linto) app
from a Stream Deck. It provides one action, **LinTO Toggle**:

- Press to start or pause streaming.
- The button shows the state: Ready / network status when idle, and the elapsed
  time, data sent or bitrate while streaming (configurable).

## Button states

The button always shows one of three icons:

| Ready | Streaming | Problem |
| :---: | :-------: | :-----: |
| ![Ready](assets/linto-ready.svg) | ![Streaming](assets/linto-streaming.svg) | ![Problem](assets/linto-ko.svg) |
| Ready to stream | Currently streaming | A problem prevents streaming |

## How it works

gnome-linto has a built-in control server. In the app, open the menu and choose
**Stream Controller**, enable the server, and note the port and password (click
the password to copy it). This plugin connects to that server over WebSocket.

## Installation

Clone this repository into StreamController's plugins directory. The target
folder must be named `ai_linto_gnomelinto` (it must match the plugin id):

```
git clone https://github.com/benjaminbellamy/gnome-linto-streamcontroller.git \
  ~/.var/app/com.core447.StreamController/data/plugins/ai_linto_gnomelinto
```

Then restart StreamController so it loads the plugin. No Python packages are
required.

To update later, pull inside that folder:

```
cd ~/.var/app/com.core447.StreamController/data/plugins/ai_linto_gnomelinto
git pull
```

## Setup

1. Add the **LinTO Toggle** action to a button.
2. In the action settings, set the **Host** (the machine running gnome-linto),
   **Port** (default 4466), and **Password** shown in the app.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
