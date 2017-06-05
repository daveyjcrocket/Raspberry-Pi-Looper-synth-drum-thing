# Raspberry-Pi-Looper-synth-drum-thing

This is a fork of otem's "Raspberry Pi Looper synth drum thing" or "piLooper" as the pd file is called. This fork is designed to run on any computer with PD Vanilla installed with any MIDI controller plugged into it.

All of the buttons and controls are done using MIDI but it's a bit buried within subpatches to actually find where the samples are being played and where you can change the note values.

As with otem's version, no samples are provided for the drum machine portions. To quote his readme:

> To add your own samples just add .wav files to the piLooper directory with names like:

> kick_01.wav - kick_24.wav

> hh_01.wav - hh_12.wav

> snare_01.wav - snare_24.wav

> crash_01.wav - crash_04.wav


# How do I install this?

* Download Pure Data Vanilla then open pd.exe (or mac equivalent) then click on "Help" -> "Find external" -> search for "comport" and install it, then search for "ggee" and install that too. You only need these if you're trying to use the external hardware, but it gets rid of the errors in the log so might as well install them.
* Download the Raspberry-Pi-Looper-synth-drum-thing zip file and unzip it.
* Open up piLooper.pd in Pure Data.
* A window with a bunch of controls should now open up. The big buttons start recording for each of the 8 loops, with the corresponding slider next to it, and the little red button is the clear button for each loop. The tall sliders below control the FX parameters.
* In PD there's normal mode and Edit Mode. Switch between the two with Ctrl + E, Cmd + E, or "Edit" -> "Edit Mode". For now make sure you're not in edit mode to make this easier.
* Click on the box labeled [pd guts]. This is a subpatch with a bunch of other subpatches in it. Clicking on it should open it, but it if you end up editing the name instead or moving it around, you are in Edit Mode. If you're in Edit Mode you can right-click / cmd-click -> "Open" instead.
* From here click on [pd set-midi-buttons]

Now the instructions on screen should be pretty straight forward, but the idea is that you're editing the message boxes to use the values of the buttons on your MIDI controller. Once you are done with the buttons, close the [pd set-midi-buttons] subpatch, and open [pd set-midi-knobs-or-sliders] and follow the same process.

# What features aren't implemented (yet)?

There are several features that I haven't implemented yet because I just haven't gotten around to it.

* The X/Y pad
* Lighting up MIDI buttons
* External audio input
* Saving / Loading songs
* Probably some other features that I haven't noticed yet

I should be able to have all these features added soon, but I might not be able to work on this until next weekend.

For more details on this project, check out otem's original repo https://github.com/otem/Raspberry-Pi-Looper-synth-drum-thing
