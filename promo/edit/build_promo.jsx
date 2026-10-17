// build_promo.jsx - builds CopyThat_promo.aep, the promo film, from nothing.
//
//   "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe" -r <this file>
//
// It makes a new project, imports the footage from dist/promo, rebuilds the cards of promo/cards/*.html as
// live After Effects layers, cuts the shots, saves promo/edit/CopyThat_promo.aep, queues the film for
// aerender (see render_promo.sh) and quits. Run it again after any change: never edit the project and this
// script apart. The cuts, speeds, captions and markers come from edit_list.jsxinc, which edit_list.py writes.
// Everything that goes wrong is written, with its line, to dist/promo/edit_build_log.txt.
//
// The cards are 1920x1080 in HTML and the film is 2560x1440, so every size and position is scaled by 4/3.
// Each card's timeline (the T = {...} of its HTML) becomes keyframes here, and its easing curve becomes the
// keyframe influence: outCubic starts fast and settles long, inOutSine is gentle at both ends.

#target aftereffects
var HERE = File($.fileName).parent;
#include "edit_list.jsxinc"

var ROOT = HERE.parent.parent;
var PROMO = new Folder(ROOT.fsName + "/dist/promo");
var CARDS_DIR = new Folder(ROOT.fsName + "/promo/cards");
var AEP = new File(HERE.fsName + "/CopyThat_promo.aep");
var LOGFILE = new File(PROMO.fsName + "/edit_build_log.txt");
var FRAMES_DIR = new Folder(PROMO.fsName + "/edit_frames");

var W = 2560, H = 1440, FPS = EDIT.fps;
var S = 4 / 3;
var GOLD = [201 / 255, 167 / 255, 106 / 255];
var INK = [242 / 255, 234 / 255, 219 / 255];
var DARK = [3 / 255, 3 / 255, 5 / 255];
var MAIN_NAME = "CopyThat Promo";

var FONT_MEDIUM = "Inter-Medium";
var FONT_DISPLAY = "InterDisplay-Light";

// Cubic-bezier control points (x1, y1, x2, y2) of the curves the cards use
var EASE = {
    outCubic: [0.215, 0.61, 0.355, 1],
    inOutSine: [0.37, 0, 0.63, 1],
    inOutCubic: [0.645, 0.045, 0.355, 1],
    outPow: [0.22, 0.58, 0.38, 1],
    outQuad: [1 / 3, 2 / 3, 2 / 3, 1],
    linear: [1 / 3, 1 / 3, 2 / 3, 2 / 3]
};

var LAST_WIDTH = 0;
var FOLDERS = {};
var ITEMS = {};

function log(msg) {
    LOGFILE.encoding = "UTF-8";
    if (LOGFILE.open("a")) {
        LOGFILE.writeln(msg);
        LOGFILE.close();
    }
}

function snap(t) {
    return Math.round(t * FPS) / FPS;
}

function P(layer, matchName) {
    return layer.property("ADBE Transform Group").property(matchName);
}

function isArray(v) {
    return v instanceof Array;
}

// ---------------------------------------------------------------- keyframes

// Keyframes for a list of segments {t0, t1, v0, v1, ease}: each segment runs one easing curve between two
// keys. A key shared by two segments takes its in-ease from the first and its out-ease from the second;
// a key at the end of a hold is flat.
function animate(prop, segs) {
    var keys = [];
    function key(t, v) {
        t = snap(t);
        for (var k = 0; k < keys.length; k++) {
            if (Math.abs(keys[k].t - t) < 1e-6) {
                return keys[k];
            }
        }
        var made = {t: t, v: v, i: null, o: null};
        keys.push(made);
        return made;
    }
    var s, k;
    for (s = 0; s < segs.length; s++) {
        var g = segs[s];
        g.a = key(g.t0, g.v0);
        g.b = key(g.t1, g.v1);
        g.a.o = g;
        g.b.i = g;
    }
    keys.sort(function (x, y) { return x.t - y.t; });
    for (k = 0; k < keys.length; k++) {
        prop.setValueAtTime(keys[k].t, keys[k].v);
    }
    var type = prop.propertyValueType;
    var spatial = (type == PropertyValueType.TwoD_SPATIAL || type == PropertyValueType.ThreeD_SPATIAL);
    function speeds(seg, which, dims) {
        // the slope of the curve at one end of the segment, per dimension (or along the path)
        var p = EASE[seg.ease];
        var dt = seg.b.t - seg.a.t;
        var factor = (which == "out") ? p[1] / p[0] : (1 - p[3]) / (1 - p[2]);
        var infl = ((which == "out") ? p[0] : (1 - p[2])) * 100;
        var v0 = isArray(seg.v0) ? seg.v0 : [seg.v0];
        var v1 = isArray(seg.v1) ? seg.v1 : [seg.v1];
        var out = [];
        var d;
        if (spatial) {
            var sum = 0;
            for (d = 0; d < v0.length; d++) {
                sum += (v1[d] - v0[d]) * (v1[d] - v0[d]);
            }
            out.push(new KeyframeEase(Math.sqrt(sum) / dt * factor, infl));
        } else {
            for (d = 0; d < dims; d++) {
                var delta = (v1[d] === undefined || v0[d] === undefined) ? 0 : (v1[d] - v0[d]);
                out.push(new KeyframeEase(delta / dt * factor, infl));
            }
        }
        return out;
    }
    for (k = 0; k < keys.length; k++) {
        var shown = prop.value;
        var dims = isArray(shown) ? shown.length : 1;
        var count = spatial ? 1 : dims;
        var flat = [];
        for (var d2 = 0; d2 < count; d2++) {
            flat.push(new KeyframeEase(0, 33.3333));
        }
        var idx = prop.nearestKeyIndex(keys[k].t);
        var inE = keys[k].i ? speeds(keys[k].i, "in", dims) : flat;
        var outE = keys[k].o ? speeds(keys[k].o, "out", dims) : flat;
        prop.setTemporalEaseAtKey(idx, inE, outE);
    }
}

function seg(t0, t1, v0, v1, ease) {
    return {t0: t0, t1: t1, v0: v0, v1: v1, ease: ease};
}

// ---------------------------------------------------------------- project helpers

function folder(name, parent) {
    var f = app.project.items.addFolder(name);
    if (parent) {
        f.parentFolder = parent;
    }
    return f;
}

function importFootage(path, sequence, name, parent, keepAlpha) {
    var f = new File(path);
    if (!f.exists) {
        throw new Error("missing footage " + path);
    }
    var io = new ImportOptions(f);
    if (sequence) {
        io.sequence = true;
        io.forceAlphabetical = false;
    }
    io.importAs = ImportAsType.FOOTAGE;
    var item = app.project.importFile(io);
    if (sequence) {
        item.mainSource.conformFrameRate = FPS;
    }
    if (!keepAlpha && item.mainSource.hasAlpha) {
        item.mainSource.alphaMode = AlphaMode.IGNORE;
    }
    item.name = name;
    item.parentFolder = parent;
    log("imported " + name + ": " + item.width + "x" + item.height + ", " + item.frameRate + " fps, " +
        Math.round(item.duration * FPS) + " frames");
    return item;
}

function makeComp(name, frames, parent) {
    var c = app.project.items.addComp(name, W, H, 1, frames / FPS, FPS);
    if (parent) {
        c.parentFolder = parent;
    }
    c.bgColor = [0, 0, 0];
    return c;
}

// Put frames [srcFrom, srcFrom + srcFrames) of a footage layer at film frames [compFrom, compFrom + outFrames),
// stretching the time to fit. Frame numbers are those of the footage file.
// A stretched layer starts on the first source frame after its in point, so an in point at exactly the right
// frame, nudged by a float error, lands a source frame late and that comp frame renders black (it did, at the
// start of every sped-up cut). The whole layer is therefore a twentieth of a frame early and its in and out
// points a quarter of a frame early, which always land on the right source frame.
function placeClip(layer, item, srcFrom, srcFrames, compFrom, outFrames) {
    var perFrame = 1 / item.frameRate;
    var stretch = 100 * outFrames / srcFrames;
    layer.stretch = stretch;
    layer.startTime = compFrom / FPS - srcFrom * perFrame * stretch / 100 - 0.05 / FPS;
    layer.inPoint = (compFrom - 0.25) / FPS;
    layer.outPoint = (compFrom + outFrames - 0.25) / FPS;
}

// Every frame of a shot must be covered by a footage layer, or it renders black: this looks, and says.
function checkCoverage(comp) {
    var frames = Math.round(comp.duration * FPS);
    var bad = [];
    for (var f = 0; f < frames; f++) {
        var t = f / FPS + 1e-6;
        var covered = false;
        for (var i = 1; i <= comp.numLayers; i++) {
            var l = comp.layer(i);
            if ((l.source instanceof FootageItem) && l.inPoint <= t && t < l.outPoint) {
                covered = true;
                break;
            }
        }
        if (!covered) {
            bad.push(f);
        }
    }
    log("coverage " + comp.name + ": " + (bad.length ? "NOT COVERED at frames " + bad.join(",") : "every frame is covered"));
}

// Where the layer's own source sits: 'cards' go on top of whatever was added before
function cardLayer(comp, card, startFrame, name) {
    var l = comp.layers.add(card);
    l.name = name;
    l.startTime = startFrame / FPS;
    l.label = 2;
    return l;
}

// ---------------------------------------------------------------- the pieces the cards are made of

function addText(comp, o) {
    var layer = comp.layers.addText(o.text);
    layer.name = o.name;
    var prop = layer.property("ADBE Text Properties").property("ADBE Text Document");
    var td = prop.value;
    td.resetCharStyle();
    td.font = o.font;
    td.fontSize = o.size;
    td.fillColor = o.color;
    td.applyFill = true;
    td.applyStroke = false;
    td.tracking = o.tracking;
    td.justification = (o.justify == "left") ? ParagraphJustification.LEFT_JUSTIFY :
        ((o.justify == "right") ? ParagraphJustification.RIGHT_JUSTIFY : ParagraphJustification.CENTER_JUSTIFY);
    prop.setValue(td);
    if (o.after) {
        o.after(prop);
    }
    var got = prop.value;
    if (got.font != o.font) {
        log("WARNING: " + o.name + " asked for font " + o.font + " and got " + got.font);
    }
    // The ink is what is centred (the cards pad the last letter's tracking for the same reason); the
    // baseline is where the card's CSS put it.
    var rect = layer.sourceRectAtTime(0, false);
    var ax = 0;
    if (o.justify == "center") {
        ax = rect.left + rect.width / 2;
    } else if (o.justify == "right") {
        ax = rect.left + rect.width;
    }
    var ay = o.aboutCenter ? -0.364 * o.size : 0;
    P(layer, "ADBE Anchor Point").setValue([ax, ay]);
    P(layer, "ADBE Position").setValue([o.x, o.baseline + ay]);
    LAST_WIDTH = rect.width;
    return layer;
}

// The baseline of a line in the cards' CSS: the top of its line box plus the half-leading and Inter's
// ascent (0.96875 em, descent 0.2412 em), in 1080 space; the result is in film pixels.
function baseline(top1080, size1080, lineHeight) {
    var halfLeading = (lineHeight - 1.2100) * size1080 / 2;
    return (top1080 + halfLeading + 0.96875 * size1080) * S;
}

// A CSS shadow, as the cards write them: dy and the blur radius in the card's 1080 pixels. CSS blurs with a
// sigma of half the radius; this effect's softness is five times its sigma (measured).
function addShadow(layer, name, dyCss, radiusCss, opacityPct) {
    var fx = layer.property("ADBE Effect Parade").addProperty("ADBE Drop Shadow");
    fx.name = name;
    fx.property(1).setValue([DARK[0], DARK[1], DARK[2], 1]);
    var op = fx.property(2);
    // the effect's opacity is 0-100 in the panel, but a script sees 0-255
    var full = (op.value > 100) ? 2.55 : 1;
    op.setValue(opacityPct * full);
    fx.property(3).setValue(180);
    fx.property(4).setValue(dyCss * S);
    fx.property(5).setValue(radiusCss * S * 2.5);
    return fx;
}

// The blurriness that gives a CSS blur(px) (a sigma of px in the card's 1080 pixels)
function blurB(cssPx) {
    return cssPx * S / 0.275;
}

function addBlur(layer, name, amount) {
    var fx = layer.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
    fx.name = name;
    fx.property(1).setValue(amount);
    return fx.property(1);
}

// A gold bar whose ends fade out: a solid with a soft-edged mask (a gradient fill is not something a script
// can set). The bar draws out from its centre by its scale.
function addRule(comp, name, cx, cy, w, h, fade) {
    w = Math.round(w);
    h = Math.max(1, Math.round(h));
    var layer = comp.layers.addSolid(GOLD, name, w, h, 1);
    P(layer, "ADBE Position").setValue([cx, cy]);
    var f = Math.round(w * fade);
    var mask = layer.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var shape = new Shape();
    shape.vertices = [[f / 2, 0], [w - f / 2, 0], [w - f / 2, h], [f / 2, h]];
    shape.inTangents = [[0, 0], [0, 0], [0, 0], [0, 0]];
    shape.outTangents = [[0, 0], [0, 0], [0, 0], [0, 0]];
    shape.closed = true;
    mask.property("ADBE Mask Shape").setValue(shape);
    mask.property("ADBE Mask Feather").setValue([f, 0]);
    return layer;
}

function pathFirst(vectors, pathName, layerName) {
    var before = vectors.property(1).name + ", " + vectors.property(2).name;
    if (vectors.property(1).name != pathName) {
        vectors.property(pathName).moveTo(1);
    }
    if (before != vectors.property(1).name + ", " + vectors.property(2).name) {
        // a script appends to the bottom of a group, and a fill above its path fills nothing
        log("shape " + layerName + ": path moved above its fill");
    }
}

function addRectShape(comp, name, left, top, width, height, color, opacityPct) {
    var layer = comp.layers.addShape();
    layer.name = name;
    P(layer, "ADBE Anchor Point").setValue([0, 0]);
    P(layer, "ADBE Position").setValue([0, 0]);
    var group = layer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    group.name = "Shape";
    var fill = group.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
    fill.property("ADBE Vector Fill Color").setValue(color);
    fill.property("ADBE Vector Fill Opacity").setValue(opacityPct);
    var rect = group.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Rect");
    rect.name = "Rect";
    rect.property("ADBE Vector Rect Size").setValue([width, height]);
    rect.property("ADBE Vector Rect Position").setValue([left + width / 2, top + height / 2]);
    pathFirst(group.property("ADBE Vectors Group"), "Rect", name);
    return layer;
}

function addEllipseShape(comp, name, cx, cy, width, height, color, opacityPct) {
    var layer = comp.layers.addShape();
    layer.name = name;
    P(layer, "ADBE Anchor Point").setValue([0, 0]);
    P(layer, "ADBE Position").setValue([0, 0]);
    var group = layer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    group.name = "Shape";
    var fill = group.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
    fill.property("ADBE Vector Fill Color").setValue(color);
    fill.property("ADBE Vector Fill Opacity").setValue(opacityPct);
    var ell = group.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Ellipse");
    ell.name = "Ellipse";
    ell.property("ADBE Vector Ellipse Size").setValue([width, height]);
    ell.property("ADBE Vector Ellipse Position").setValue([cx, cy]);
    pathFirst(group.property("ADBE Vectors Group"), "Ellipse", name);
    return layer;
}

function fullSolid(comp, name, color) {
    return comp.layers.addSolid(color, name, W, H, 1);
}

// opacity in at [a, b] with `easeIn`, out at [c, d] with inOutSine; top value `top`
function fadeInOut(layer, inRange, outRange, top, easeIn) {
    var segs = [];
    if (inRange) {
        segs.push(seg(inRange[0], inRange[1], 0, top, easeIn || "outCubic"));
    }
    if (outRange) {
        segs.push(seg(outRange[0], outRange[1], top, 0, "inOutSine"));
    }
    animate(P(layer, "ADBE Opacity"), segs);
}

// ---------------------------------------------------------------- cards

// statement.html: one big line with a short gold rule under it, over the render.
function buildStatement(text, y1080, parent) {
    var comp = makeComp("Statement - " + text, 45, parent);
    var last = comp.duration - 1 / FPS;
    var outStart = Math.max(last - 0.20, 0.30);
    var line = addText(comp, {
        name: "Line", text: text, font: FONT_DISPLAY, size: 150 * S, tracking: -28, color: INK, justify: "center",
        x: W / 2, baseline: (y1080 + 54.6) * S
    });
    var baseY = (y1080 + 54.6) * S;
    // the dark glow that lets it sit on bright petals: a tight edge, a soft drop and a wide haze
    addShadow(line, "Shadow edge", 0, 2, 40);
    addShadow(line, "Shadow drop", 3, 14, 52);
    addShadow(line, "Shadow soft", 8, 52, 55);
    addShadow(line, "Shadow haze", 0, 120, 40);
    var blur = addBlur(line, "Focus", blurB(6));
    fadeInOut(line, [0, 0.25], [outStart, last], 100);
    animate(P(line, "ADBE Position"), [
        seg(0, 0.25, [W / 2, baseY + 12 * S], [W / 2, baseY], "outCubic"),
        seg(outStart, last, [W / 2, baseY], [W / 2, baseY - 6 * S], "inOutSine")]);
    animate(blur, [seg(0, 0.25, blurB(6), 0, "outCubic")]);

    var rule = addRule(comp, "Rule", W / 2, (y1080 + 111 + 1.5) * S, 220 * S, 3 * S, 0.18);
    animate(P(rule, "ADBE Scale"), [seg(0.06, 0.30, [0, 100], [100, 100], "inOutCubic")]);
    animate(P(rule, "ADBE Opacity"), [seg(0.06, 0.143, 0, 100, "linear"), seg(outStart, last, 100, 0, "inOutSine")]);
    line.moveToBeginning();
    return comp;
}

// lower_third.html: a dark slab with soft edges, a sharp gold rule and the caption, for the demo.
function buildLowerThird(name, caption, frames, parent, useMatte) {
    var comp = makeComp(name, frames, parent);
    var last = comp.duration - 1 / FPS;
    var outStart = Math.max(last - 0.25, 0.30);
    var barLeft = 96 * S, barTop = (1080 - 128 - 96) * S, barBottom = (1080 - 128) * S;

    var text = addText(comp, {
        name: "Caption", text: caption, font: FONT_MEDIUM, size: 40 * S, tracking: -4, color: INK, justify: "left",
        x: (96 + 40) * S, baseline: baseline(1080 - 128 - 96, 40, 1.2) + 24 * S
    });
    var textWidth = LAST_WIDTH;
    var rule = comp.layers.addSolid(GOLD, "Gold rule", Math.round(3 * S), Math.round(barBottom - barTop), 1);
    P(rule, "ADBE Position").setValue([barLeft + 3 * S / 2, (barTop + barBottom) / 2]);
    // top to bottom: a lighter gold to a deeper one (the card's gradient, two stops)
    var ramp = rule.property("ADBE Effect Parade").addProperty("ADBE Ramp");
    ramp.name = "Gold gradient";
    ramp.property(1).setValue([0, 0]);
    ramp.property(2).setValue([221 / 255, 196 / 255, 140 / 255, 1]);
    ramp.property(3).setValue([0, rule.height]);
    ramp.property(4).setValue([191 / 255, 157 / 255, 97 / 255, 1]);

    // The slab is blurred, and a blur would soften its left side too: a matte cuts it at the gold rule, so
    // that edge stays sharp and the other three fade out softly. It sizes itself to the caption.
    var slabW = textWidth + 181.3;
    var slabLeft = barLeft - 40 * S;
    var slabTop = barTop - 8 * S, slabH = (barBottom - barTop) + 16 * S;
    var slab = addRectShape(comp, "Slab", slabLeft, slabTop, slabW, slabH, [10 / 255, 10 / 255, 12 / 255], 72);
    var rect = slab.property("ADBE Root Vectors Group").property("Shape").property("ADBE Vectors Group").property("Rect");
    rect.property("ADBE Vector Rect Size").expression =
        'var w = 0;\ntry { w = thisComp.layer("Caption").sourceRectAtTime(time, false).width; } catch (e) { w = 0; }\n' +
        'if (isNaN(w) || w <= 0) { w = ' + textWidth + '; }\n[w + 181.3, ' + slabH + '];';
    rect.property("ADBE Vector Rect Position").expression =
        'var s = content("Shape").content("Rect").size;\n[' + slabLeft + ' + s[0] / 2, ' + (slabTop + slabH / 2) + '];';
    addBlur(slab, "Soft edge", blurB(9));
    var clip = null;
    if (useMatte) {
        clip = addRectShape(comp, "Slab matte (cuts at the gold rule)", barLeft, 0, 3200, H, [1, 1, 1], 100);
        try {
            slab.setTrackMatte(clip, TrackMatteType.ALPHA);
        } catch (e) {
            log("track matte: " + e.toString());
        }
        clip.enabled = false;
    }

    var slide = comp.layers.addNull();
    slide.name = "Bar slide";
    P(slide, "ADBE Anchor Point").setValue([0, 0]);
    P(slide, "ADBE Position").setValue([0, 0]);
    var parts = [text, rule, slab];
    if (clip) {
        parts.push(clip);
    }
    for (var i = 0; i < parts.length; i++) {
        parts[i].parent = slide;
    }
    animate(P(slide, "ADBE Position"), [
        seg(0, 0.30, [-24 * S, 0], [0, 0], "outCubic"),
        seg(outStart, last, [0, 0], [-12 * S, 0], "inOutSine")]);
    fadeInOut(slab, [0, 0.30], [outStart, last], 100);
    fadeInOut(rule, [0, 0.30], [outStart, last], 100);
    animate(P(text, "ADBE Opacity"), [seg(0.06, 0.30, 0, 100, "outCubic"), seg(outStart, last, 100, 0, "inOutSine")]);
    slide.enabled = false;
    slide.moveToEnd();
    slab.moveToEnd();
    slide.moveToEnd();
    rule.moveToBeginning();
    text.moveToBeginning();
    return comp;
}

// tag.html: a few small words bottom right, a plain fade each way.
function buildTag(text, frames, parent) {
    var comp = makeComp("Tag - " + text, frames, parent);
    var last = comp.duration - 1 / FPS;
    var layer = addText(comp, {
        name: "Tag", text: text, font: FONT_MEDIUM, size: 26 * S, tracking: 40, justify: "right",
        color: [INK[0] * 0.85 + DARK[0] * 0.15, INK[1] * 0.85 + DARK[1] * 0.15, INK[2] * 0.85 + DARK[2] * 0.15],
        x: (1920 - 96) * S, baseline: baseline(1080 - 120 - 31.2, 26, 1.2)
    });
    addShadow(layer, "Shadow", 1, 14, 60);
    animate(P(layer, "ADBE Opacity"), [
        seg(0, 0.30, 0, 100, "inOutSine"), seg(Math.max(last - 0.30, 0.30), last, 100, 0, "inOutSine")]);
    return comp;
}

// title_short.html: the wordmark wipes in, the rule draws out, the tagline rises, then it fades to black.
function buildTitle(parent) {
    var comp = makeComp("Title card", 60, parent);
    var last = 59 / FPS;
    var cx = W / 2;

    var black = fullSolid(comp, "Black", [0, 0, 0]);
    var bg = fullSolid(comp, "Studio backdrop", [0, 0, 0]);
    var ramp = bg.property("ADBE Effect Parade").addProperty("ADBE Ramp");
    ramp.name = "Backdrop gradient";
    ramp.property(1).setValue([cx, 0.44 * H]);
    ramp.property(2).setValue([21 / 255, 23 / 255, 29 / 255, 1]);
    ramp.property(3).setValue([cx + 1250, 0.44 * H]);
    ramp.property(4).setValue([3 / 255, 3 / 255, 4 / 255, 1]);
    ramp.property(5).setValue(2);
    animate(P(bg, "ADBE Opacity"), [seg(0, 0.45, 0, 100, "inOutSine")]);

    var glow = addEllipseShape(comp, "Gold glow", cx, 0.41 * H, 1520, 600, GOLD, 17);
    addBlur(glow, "Soft", 300);
    animate(P(glow, "ADBE Opacity"), [seg(0.17, 1.20, 0, 100, "outCubic")]);

    var grain = comp.layers.add(ITEMS.grain);
    grain.name = "Grain (grain.png, tiled)";
    var tile = grain.property("ADBE Effect Parade").addProperty("ADBE Tile");
    tile.name = "Tile";
    tile.property(4).setValue(400);
    tile.property(5).setValue(400);
    P(grain, "ADBE Scale").setValue([100 * S, 100 * S]);
    P(grain, "ADBE Position").setValue([cx, H / 2]);
    animate(P(grain, "ADBE Opacity"), [seg(0, 0.45, 0, 6, "inOutSine")]);

    var mark = addText(comp, {
        name: "Wordmark", text: "CopyThat", font: FONT_DISPLAY, size: 214 * S, tracking: -35, color: INK,
        justify: "center", aboutCenter: true, x: cx, baseline: (421.46 + 0.364 * 214) * S
    });
    var markWidth = LAST_WIDTH;
    var wipe = mark.property("ADBE Effect Parade").addProperty("ADBE Linear Wipe");
    wipe.name = "Wipe in";
    wipe.property(2).setValue(270);
    wipe.property(3).setValue(Math.round(0.30 * markWidth));
    animate(wipe.property(1), [seg(0.10, 0.92, 100, 0, "inOutSine")]);
    var sharpen = addBlur(mark, "Focus", blurB(18));
    animate(sharpen, [seg(0.10, 1.12, blurB(18), 0, "outPow")]);
    animate(P(mark, "ADBE Opacity"), [seg(0.10, 0.35, 0, 100, "linear")]);
    animate(P(mark, "ADBE Scale"), [seg(0.10, 1.30, [104.5, 104.5], [100, 100], "outCubic")]);

    var rule = addRule(comp, "Rule", cx, 587 * S, 440 * S, 2 * S, 0.22);
    animate(P(rule, "ADBE Scale"), [seg(0.72, 1.04, [0, 100], [100, 100], "inOutCubic")]);
    animate(P(rule, "ADBE Opacity"), [seg(0.72, 0.80, 0, 100, "linear")]);

    var tagline = addText(comp, {
        name: "Tagline", text: "Record a move. Get a slider.", font: FONT_DISPLAY, size: 50 * S, tracking: 12,
        color: INK, justify: "center", x: cx, baseline: baseline(638, 50, 1.2)
    });
    var tagBlur = addBlur(tagline, "Focus", blurB(7));
    animate(tagBlur, [seg(0.92, 1.28, blurB(7), 0, "outCubic")]);
    animate(P(tagline, "ADBE Opacity"), [seg(0.92, 1.28, 0, 100, "outCubic")]);
    var tagY = baseline(638, 50, 1.2);
    animate(P(tagline, "ADBE Position"), [seg(0.92, 1.28, [cx, tagY + 22 * S], [cx, tagY], "outCubic")]);

    // a slow push-in on the type, so the hold never feels frozen
    var push = comp.layers.addNull();
    push.name = "Push-in";
    P(push, "ADBE Anchor Point").setValue([cx, H / 2]);
    P(push, "ADBE Position").setValue([cx, H / 2]);
    animate(P(push, "ADBE Scale"), [seg(0, 2.0, [100, 100], [102.8, 102.8], "outCubic")]);
    push.enabled = false;
    mark.parent = push;
    rule.parent = push;
    tagline.parent = push;

    var fade = fullSolid(comp, "Fade to black", [0, 0, 0]);
    animate(P(fade, "ADBE Opacity"), [seg(1.70, last, 0, 100, "inOutSine")]);
    fade.moveToBeginning();
    return comp;
}

// end.html: the shade, then four lines coming up one after another.
function buildEnd(parent) {
    var comp = makeComp("End card", 120, parent);
    var cx = W / 2;

    function rise(layer, t0, t1, dy, blurAmount, baseY) {
        animate(P(layer, "ADBE Opacity"), [seg(t0, t1, 0, 100, "outCubic")]);
        animate(P(layer, "ADBE Position"), [seg(t0, t1, [cx, baseY + dy * S], [cx, baseY], "outCubic")]);
        animate(addBlur(layer, "Focus", blurB(blurAmount)), [seg(t0, t1, blurB(blurAmount), 0, "outCubic")]);
    }

    var by = addText(comp, {
        name: "Credit", text: "by NemVe3D  \u00B7  creators.sa/nemve", font: FONT_MEDIUM, size: 25 * S, tracking: 120,
        color: [0.74, 0.72, 0.67], justify: "center", x: cx, baseline: baseline(1001, 25, 1.2),
        after: function (prop) {
            // the name in warm white, the dot and the address in gold
            try {
                var td = prop.value;
                var range = td.characterRange(10, td.text.length);
                range.fillColor = GOLD;
                range.applyFill = true;
                prop.setValue(td);
            } catch (e) {
                log("note: the credit could not be coloured in parts (" + e.toString() + "); it is one colour");
            }
        }
    });
    addShadow(by, "Shadow", 2, 28, 55);
    rise(by, 0.65, 1.45, 10, 3, baseline(1001, 25, 1.2));

    var shop = addText(comp, {
        name: "Superhive", text: "Now on Superhive", font: FONT_MEDIUM, size: 29 * S, tracking: 100, color: GOLD,
        justify: "center", x: cx, baseline: baseline(956, 29, 1.2)
    });
    addShadow(shop, "Shadow", 2, 28, 55);
    rise(shop, 0.50, 1.30, 12, 4, baseline(956, 29, 1.2));

    var tag = addText(comp, {
        name: "Tagline", text: "Record a move. Get a slider.", font: FONT_DISPLAY, size: 40 * S, tracking: 12,
        color: INK, justify: "center", x: cx, baseline: baseline(904, 40, 1.2)
    });
    addShadow(tag, "Shadow", 2, 28, 55);
    rise(tag, 0.35, 1.15, 14, 5, baseline(904, 40, 1.2));

    var mark = addText(comp, {
        name: "Wordmark", text: "CopyThat", font: FONT_DISPLAY, size: 120 * S, tracking: -35, color: INK,
        justify: "center", x: cx, baseline: baseline(766, 120, 1)
    });
    addShadow(mark, "Shadow", 2, 28, 55);
    rise(mark, 0.10, 1.00, 18, 8, baseline(766, 120, 1));

    // the shade: clear above y = 560 (of 1080), eased to near black at the bottom edge, and a soft pool
    // right behind the text
    var pool = addEllipseShape(comp, "Pool", cx, 900 * S, 1900, 560, DARK, 45);
    addBlur(pool, "Soft", 240);
    animate(P(pool, "ADBE Opacity"), [seg(0, 1.0, 0, 100, "inOutSine")]);
    var shade = fullSolid(comp, "Shade", DARK);
    var mid = (560 + 1080) / 2 * S, spread = (1080 - 560) * S;
    var mask = shade.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var shape = new Shape();
    shape.vertices = [[-20, mid], [W + 20, mid], [W + 20, H + 600], [-20, H + 600]];
    shape.inTangents = [[0, 0], [0, 0], [0, 0], [0, 0]];
    shape.outTangents = [[0, 0], [0, 0], [0, 0], [0, 0]];
    shape.closed = true;
    mask.property("ADBE Mask Shape").setValue(shape);
    mask.property("ADBE Mask Feather").setValue([0, Math.round(spread * 0.65)]);
    mask.property("ADBE Mask Opacity").setValue(93);
    animate(P(shade, "ADBE Opacity"), [seg(0, 1.0, 0, 100, "inOutSine")]);
    pool.moveToEnd();
    shade.moveToEnd();
    return comp;
}

// ---------------------------------------------------------------- the shots

function shotComp(index) {
    var s = EDIT.shots[index];
    return makeComp(s.name, s.frames, FOLDERS.shots);
}

function buildHookShot(index, letter, statementIndex, statementComp) {
    var comp = shotComp(index);
    var item = ITEMS["hook" + letter];
    var layer = comp.layers.add(item);
    layer.name = "Hook " + letter + " (Cycles)";
    var frames = EDIT.hooks[letter].frames;
    placeClip(layer, item, 0, frames, 0, EDIT.shots[index].frames);
    cardLayer(comp, statementComp, 0, "Statement: " + EDIT.statements[statementIndex].text);
    return comp;
}

function buildSliderShot(ltComp) {
    var comp = shotComp(3);
    var item = ITEMS.slider;
    var layer = comp.layers.add(item);
    layer.name = "Slider recording";
    var sl = EDIT.slider;
    placeClip(layer, item, sl.start, sl.src_frames, 0, EDIT.shots[3].frames);
    layer.label = 9;
    cardLayer(comp, ltComp, 0, "Lower third: " + sl.caption);
    return comp;
}

function buildDemoShot(lowerThirds) {
    var comp = shotComp(5);
    var item = ITEMS.main;
    var segs = EDIT.demo.segments;
    var labels = {D: 11, M: 9, P: 8};
    var words = {D: "dialog", M: "moves", P: "pause"};
    var beats = EDIT.demo.beats;
    // the first cut on top, so the clips read down the layer stack in the order they play
    for (var i = segs.length - 1; i >= 0; i--) {
        var s = segs[i];
        var layer = comp.layers.add(item);
        var speed = s.src_frames / s.frames;
        layer.name = "Beat " + (s.beat + 1) + " " + beats[s.beat].name + " | " + words[s.kind] + " " +
            speed.toFixed(2) + "x | src " + (Math.round((s.src - EDIT.demo.flash) / FPS * 100) / 100) + " s";
        placeClip(layer, item, s.src, s.src_frames, s.start, s.frames);
        layer.label = labels[s.kind];
    }
    for (var b = 0; b < beats.length; b++) {
        cardLayer(comp, lowerThirds[b], beats[b].start, "Lower third " + (b + 1) + ": " + beats[b].caption);
        var m = new MarkerValue("Beat " + (b + 1) + ": " + beats[b].name + " - " + beats[b].caption);
        comp.markerProperty.setValueAtTime(beats[b].start / FPS, m);
    }
    return comp;
}

function buildMatchCut(tagComp) {
    var comp = shotComp(6);
    var frames = EDIT.shots[6].frames;
    var mc = EDIT.match_cut;
    var outro = comp.layers.add(ITEMS.outro);
    outro.name = "Outro (Cycles), same frames as the bloom";
    placeClip(outro, ITEMS.outro, 0, frames, 0, frames);
    var d0 = mc.dissolve_start / FPS, d1 = (mc.dissolve_start + mc.dissolve_frames) / FPS;
    animate(P(outro, "ADBE Opacity"), [seg(d0, d1, 0, 100, "inOutSine")]);
    var bloom = comp.layers.add(ITEMS.bloom);
    bloom.name = "Viewport bloom (Blender camera view, rendered frame by frame)";
    placeClip(bloom, ITEMS.bloom, 0, frames, 0, frames);
    bloom.moveToEnd();
    cardLayer(comp, tagComp, mc.tag_start, "Tag: Rendered in Cycles");
    var m = new MarkerValue("Dissolve: the viewport bloom into the Cycles render");
    comp.markerProperty.setValueAtTime(d0, m);
    return comp;
}

function buildEndShot(endComp) {
    var comp = shotComp(7);
    var frames = EDIT.shots[7].frames;
    var firstFrame = EDIT.shots[6].frames;               // the outro goes on from where shot 7 stopped
    var lastFrame = EDIT.outro.frames - 1;
    var outro = comp.layers.add(ITEMS.outro);
    outro.name = "Outro (Cycles), settling to its last frame";
    // The render has fewer frames left than the shot is long: it plays on at normal speed and slows to a
    // stop on its last frame while the card comes up (an ease-out, so there is no jump of speed at the cut).
    outro.timeRemapEnabled = true;
    var remap = outro.property("ADBE Time Remapping");
    var v0 = firstFrame / FPS, v1 = lastFrame / FPS;
    var t1 = frames / FPS;
    animate(remap, [seg(0, t1, v0, v1, "outQuad")]);
    for (var q = remap.numKeys; q >= 1; q--) {
        var kt = remap.keyTime(q);
        if (Math.abs(kt) > 1e-4 && Math.abs(kt - t1) > 1e-4) {
            remap.removeKey(q);
        }
    }
    outro.outPoint = t1;
    cardLayer(comp, endComp, 0, "End card");
    return comp;
}

// ---------------------------------------------------------------- main

function build() {
    app.newProject();
    app.project.bitsPerChannel = 16;
    log("After Effects " + app.version + ", project at 16 bits per channel");

    FOLDERS.footage = folder("Footage");
    FOLDERS.hooks = folder("Hooks", FOLDERS.footage);
    FOLDERS.rec = folder("Recording", FOLDERS.footage);
    FOLDERS.render = folder("Render", FOLDERS.footage);
    FOLDERS.cards = folder("Cards");
    FOLDERS.shots = folder("Shots");

    var promo = PROMO.fsName;
    ITEMS.hookA = importFootage(promo + "/" + EDIT.hooks.A.folder + "/" + EDIT.hooks.A.first, true, "hook_A (frames 30-90)", FOLDERS.hooks);
    ITEMS.hookB = importFootage(promo + "/" + EDIT.hooks.B.folder + "/" + EDIT.hooks.B.first, true, "hook_B (frames 106-150)", FOLDERS.hooks);
    ITEMS.hookC = importFootage(promo + "/" + EDIT.hooks.C.folder + "/" + EDIT.hooks.C.first, true, "hook_C (frames 152-197)", FOLDERS.hooks);
    ITEMS.main = importFootage(promo + "/" + EDIT.demo.file, false, "Main recording (Blender window, ProRes 4444)", FOLDERS.rec);
    ITEMS.slider = importFootage(promo + "/" + EDIT.slider.file, false, "Slider recording (ProRes 4444)", FOLDERS.rec);
    ITEMS.outro = importFootage(promo + "/" + EDIT.outro.folder + "/" + EDIT.outro.first, true, "Outro (Cycles, frames 1-210)", FOLDERS.render);
    ITEMS.bloom = importFootage(promo + "/" + EDIT.bloom.folder + "/" + EDIT.bloom.first, true, "Viewport bloom (frames 1-151)", FOLDERS.render);
    ITEMS.grain = importFootage(CARDS_DIR.fsName + "/grain.png", false, "grain.png", FOLDERS.cards, true);
    log("footage imported");

    // the cards
    var statements = [];
    for (var i = 0; i < EDIT.statements.length; i++) {
        statements.push(buildStatement(EDIT.statements[i].text, EDIT.statements[i].y, FOLDERS.cards));
    }
    log("statements built");
    var title = buildTitle(FOLDERS.cards);
    log("title built");
    var lowerThirds = [];
    for (var b = 0; b < EDIT.demo.beats.length; b++) {
        var beat = EDIT.demo.beats[b];
        lowerThirds.push(buildLowerThird("Lower third " + (b + 1) + " - " + beat.name, beat.caption, beat.lt_frames, FOLDERS.cards, true));
    }
    var sliderLT = buildLowerThird("Lower third - slider", EDIT.slider.caption,
        Math.min(EDIT.shots[3].frames - 3, 120), FOLDERS.cards, true);
    log("lower thirds built");
    var tagFrames = EDIT.shots[6].frames - EDIT.match_cut.tag_start;
    var tag = buildTag("Rendered in Cycles", tagFrames, FOLDERS.cards);
    var end = buildEnd(FOLDERS.cards);
    log("tag and end card built");

    // the shots
    var shots = [];
    shots.push(buildHookShot(0, "A", 0, statements[0]));
    shots.push(buildHookShot(1, "B", 1, statements[1]));
    shots.push(buildHookShot(2, "C", 2, statements[2]));
    shots.push(buildSliderShot(sliderLT));
    var titleShot = shotComp(4);
    cardLayer(titleShot, title, 0, "Title card");
    shots.push(titleShot);
    shots.push(buildDemoShot(lowerThirds));
    shots.push(buildMatchCut(tag));
    shots.push(buildEndShot(end));
    for (var c = 0; c < shots.length; c++) {
        if (c != 4) {
            checkCoverage(shots[c]);
        }
    }
    log("shots built");

    // the film
    var main = makeComp(MAIN_NAME, EDIT.frames, null);
    for (var k = 0; k < shots.length; k++) {
        var layer = main.layers.add(shots[k]);
        layer.name = EDIT.shots[k].name;
        layer.startTime = EDIT.shots[k].start / FPS;
        layer.label = (k % 2) ? 5 : 8;
    }
    for (var j = 0; j < EDIT.markers.length; j++) {
        var mk = new MarkerValue(EDIT.markers[j].comment);
        main.markerProperty.setValueAtTime(EDIT.markers[j].frame / FPS, mk);
    }
    log("main comp built: " + main.duration + " s, " + main.layers.length + " layers");

    // the solids the layers made go in a folder of their own
    var solids = folder("Solids", FOLDERS.cards);
    for (var n = app.project.numItems; n >= 1; n--) {
        var it = app.project.item(n);
        if ((it instanceof FootageItem) && (it.mainSource instanceof SolidSource) && it.parentFolder != solids) {
            it.parentFolder = solids;
        }
    }

    // for aerender: a PNG sequence, which render_promo.sh encodes with ffmpeg. This After Effects lists no PNG
    // template and will not let a script change the format, but it keeps two hidden ones (8 and 16 bits).
    FRAMES_DIR.create();
    var queued = app.project.renderQueue.items.add(main);
    queued.applyTemplate("Best Settings");
    var om = queued.outputModule(1);
    om.applyTemplate("_HIDDEN X-Factor 8");
    om.file = new File(FRAMES_DIR.fsName + "/promo_[#####].png");
    var shown = om.getSettings(GetSettingsFormat.STRING);
    log("render queue: " + om.file.fsName + " | Format " + shown["Format"] + ", Channels " + shown["Channels"] +
        ", Depth " + shown["Depth"]);
}

function run() {
    var failed = false;
    LOGFILE.encoding = "UTF-8";
    if (LOGFILE.open("w")) {
        LOGFILE.writeln("build_promo.jsx started " + (new Date()).toString());
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
