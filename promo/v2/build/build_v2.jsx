// build_v2.jsx - builds promo/v2/CopyThat_promo_v2.aep: the film's rendered segments and the two stems on one timeline.
//
//   "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe" -r <this file>
//
// One composition, 2560x1440 at 60 fps (the length of timeline.json): the beats as layers (dist/promo/v2/segments), the voiceover and the
// sound effects as two audio layers (dist/promo/v2/vo.wav, sfx.wav; no music, add yours), and a marker for every beat
// and every voiceover line, taken from promo/v2/timeline.json. Run it again after a re-render.
// Nothing is shown in a dialog: everything that goes wrong is written, with its line, to dist/promo/v2/ae_build_log.txt.
// It quits After Effects by itself when it is done, and never touches an After Effects that was running already
// (promo/v2/build/run_ae.ps1 refuses to start in that case).

#target aftereffects
var HERE = File($.fileName).parent;                          // promo/v2/build
var V2 = HERE.parent;                                        // promo/v2
var OUT = new Folder(V2.parent.parent.fsName + "/dist/promo/v2");
var AEP = new File(V2.fsName + "/CopyThat_promo_v2.aep");
var LOGFILE = new File(OUT.fsName + "/ae_build_log.txt");
var W = 2560, H = 1440, FPS = 60;

function log(msg) {
    LOGFILE.encoding = "UTF-8";
    if (LOGFILE.open("a")) {
        LOGFILE.writeln(msg);
        LOGFILE.close();
    }
}

function readJson(file) {
    file.encoding = "UTF-8";
    file.open("r");
    var text = file.read();
    file.close();
    return eval("(" + text + ")");                           // ExtendScript has no JSON.parse
}

function importFile(path, name, parent) {
    var f = new File(path);
    if (!f.exists) {
        throw new Error("missing " + path);
    }
    var item = app.project.importFile(new ImportOptions(f));
    item.name = name;
    item.parentFolder = parent;
    return item;
}

function build() {
    app.newProject();
    app.project.bitsPerChannel = 8;
    var T = readJson(new File(V2.fsName + "/timeline.json"));
    log("After Effects " + app.version + ", " + T.beats.length + " beats, " + T.duration + " s");

    var segFolder = app.project.items.addFolder("Rendered segments");
    var audioFolder = app.project.items.addFolder("Audio stems");
    var main = app.project.items.addComp("CopyThat promo v2.3", W, H, 1, T.duration, FPS);
    main.bgColor = [0.04, 0.04, 0.05];

    // one layer per beat, in order, each at its start time
    var segDir = new Folder(OUT.fsName + "/segments");
    for (var i = 0; i < T.beats.length; i++) {
        var b = T.beats[i];
        var n = (i + 1 < 10 ? "0" : "") + (i + 1);
        var item = importFile(segDir.fsName + "/" + n + "_" + b.id + ".mp4", n + " " + b.name, segFolder);
        var layer = main.layers.add(item);
        layer.name = n + " " + b.name;
        layer.startTime = b.start;
        layer.label = (i % 2) ? 5 : 8;
        try { layer.audioEnabled = false; } catch (e0) { /* the segments carry no sound, so there may be nothing to switch off */ }
    }

    // the stems, whole length, at the start
    var stems = [["vo.wav", "Voiceover (stem)", 9], ["sfx.wav", "Sound effects (stem)", 11]];
    for (var s = 0; s < stems.length; s++) {
        var a = importFile(OUT.fsName + "/" + stems[s][0], stems[s][1], audioFolder);
        var al = main.layers.add(a);
        al.name = stems[s][1];
        al.startTime = 0;
        al.label = stems[s][2];
    }

    // markers: the beat grid, then what the voice says and when
    for (var m = 0; m < T.markers.length; m++) {
        main.markerProperty.setValueAtTime(T.markers[m].t, new MarkerValue(T.markers[m].name));
    }
    for (var id in T.lines) {
        var ln = T.lines[id];
        var mv = new MarkerValue("VO: " + ln.text);
        mv.duration = ln.speech_end - ln.speech_start;
        main.markerProperty.setValueAtTime(ln.speech_start + 0.0005, mv);
    }
    log("main comp: " + main.layers.length + " layers, " + main.markerProperty.numKeys + " markers");
}

function run() {
    var failed = false;
    OUT.create();
    LOGFILE.encoding = "UTF-8";
    if (LOGFILE.open("w")) {
        LOGFILE.writeln("build_v2.jsx started " + (new Date()).toString());
        LOGFILE.close();
    }
    app.beginSuppressDialogs();
    try {
        build();
    } catch (e) {
        failed = true;
        log("ERROR line " + e.line + " (" + e.fileName + "): " + e.toString());
    }
    try {
        app.project.save(AEP);
        log("saved " + AEP.fsName);
    } catch (e2) {
        failed = true;
        log("SAVE FAILED: " + e2.toString());
    }
    log(failed ? "SCRIPT END (with errors)" : "SCRIPT END (ok)");
    app.endSuppressDialogs(false);
    app.quit();
}

run();
