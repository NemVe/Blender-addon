// Small maths for posing the film: every value is a pure function of the time, so a frame is the same however it is reached.

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const mix = (a, b, t) => a + (b - a) * t;
export const ramp = (t, a, b) => clamp((t - a) / (b - a));           // 0 before a, 1 after b
export const e2 = x => 1 - (1 - x) ** 2;                              // ease out
export const e3 = x => 1 - (1 - x) ** 3;
export const e5 = x => 1 - (1 - x) ** 5;
export const ei3 = x => x ** 3;                                       // ease in
export const io = x => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);   // ease in and out
export const io2 = x => (x < 0.5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2);
export const lin = x => x;
export const bk = x => { const c = 1.70158; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2; };   // ease out with overshoot
export const hump = x => Math.sin(Math.PI * clamp(x));
export const D2R = Math.PI / 180;

// Keyframes: kf(t, [[t0, v0], [t1, v1, ease], ...]). A value is a number or an array of numbers; each segment
// runs with the ease named on its end key (ease in and out when none).
export function kf(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    if (t <= keys[i][0]) {
      const [t0, a] = keys[i - 1];
      const [t1, b, ez] = keys[i];
      const u = (ez || io)(ramp(t, t0, t1));
      return Array.isArray(a) ? a.map((x, j) => mix(x, b[j], u)) : mix(a, b, u);
    }
  }
  return keys[keys.length - 1][1];
}

export function rng(seed) {
  let s = (seed >>> 0) || 1;
  return () => {
    s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

// Press state for a button that is clicked at time tc: lit for a moment.
export const pressed = (lt, tc, len = 0.18) => lt >= tc && lt < tc + len;
