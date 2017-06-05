# Raspberry-Pi-Looper-synth-drum-thing
This is a fork of otem's "Raspberry Pi Looper synth drum thing" or "piLooper" as the pd file is called. This fork is designed to run on any computer with PD Vanilla installed with any MIDI controller plugged into it.

 All of the buttons and controls are done using MIDI but it's a bit buried within subpatches to actually find where the samples are being played and where you can change the note values.

* Download Pure Data Vanilla then open pd.exe (or mac equivalent) then click on "Help" -> "Find external" -> search for "comport" and install it, then search for "ggee" and install that too. You only need these if you're trying to use the external hardware, but it gets rid of the errors in the log so might as well install them.
* Download the Raspberry-Pi-Looper-synth-drum-thing zip file and unzip it.
* Open up piLooper.pd in Pure Data.
* A winodow with a bunch of controls should now open up. The big buttons start recording for each of the 8 loops, with the corresponding slider next to it, and the little red button is the clear button for each loop. The tall sliders below control the FX parameters.
* In PD there's normal mode and Edit Mode. Switch between the two with Ctrl + E, Cmd + E, or "Edit" -> "Edit Mode". For now make sure you're not in edit mode to make this easier.
* Click on the box labeled [pd guts]. This is a subpatch with a bunch of other subpatches in it. Clicking on it should open it, but it if you end up editing the name instead or moving it around, you are in Edit Mode. If you're in Edit Mode you can right-click / cmd-click -> "Open" instead.
* From here click on [pd set-midi-buttons]

Now you should see a 4x4 grid of [samp] objects with a bunch of different arguments. For example, the first one is [samp 60 /btn13 snare_04.wav]. The "60" is the midi node, the "/btn13" I believe is for the screen's GUI so lets ignore it edit: the "/btn13" is for the synth patch to know what note you are pressing, and the "snare_04.wav" is the path to the sample that is played when you hit midi note 60. If you want to edit these values, switch over to edit mode "Edit" -> "Edit Mode" or ctrl + e (cmd + e) and then click the box and change the data.

To configure your MIDI controller buttons and knobs, 

Check out his project readme for more details. https://github.com/otem/Raspberry-Pi-Looper-synth-drum-thing
