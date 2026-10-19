// Visual 5×8 character raster. ASCII artwork is local; no browser fonts or downloads.
// The physical LCD's ROM variant is unknown: this is not a verified ROM dump.
// Custom characters always use the eight CGRAM rows written by the actual C code.
const lcdAsciiRows = `
20 00 00 00 00 00 00 00
21 04 04 04 04 04 00 04
22 0a 0a 0a 00 00 00 00
23 0a 1f 0a 0a 1f 0a 00
24 04 0f 14 0e 05 1e 04
25 19 19 02 04 08 13 13
26 0c 12 14 08 15 12 0d
27 04 04 08 00 00 00 00
28 02 04 08 08 08 04 02
29 08 04 02 02 02 04 08
2a 00 04 15 0e 15 04 00
2b 00 04 04 1f 04 04 00
2c 00 00 00 00 04 04 08
2d 00 00 00 1f 00 00 00
2e 00 00 00 00 00 0c 0c
2f 01 02 02 04 08 08 10
30 0e 11 13 15 19 11 0e
31 04 0c 04 04 04 04 0e
32 0e 11 01 02 04 08 1f
33 1f 02 04 02 01 11 0e
34 02 06 0a 12 1f 02 02
35 1f 10 1e 01 01 11 0e
36 06 08 10 1e 11 11 0e
37 1f 01 02 04 08 08 08
38 0e 11 11 0e 11 11 0e
39 0e 11 11 0f 01 02 0c
3a 00 0c 0c 00 0c 0c 00
3b 00 0c 0c 00 04 04 08
3c 02 04 08 10 08 04 02
3d 00 00 1f 00 1f 00 00
3e 08 04 02 01 02 04 08
3f 0e 11 01 02 04 00 04
40 0e 11 17 15 17 10 0e
41 0e 11 11 1f 11 11 11
42 1e 11 11 1e 11 11 1e
43 0e 11 10 10 10 11 0e
44 1c 12 11 11 11 12 1c
45 1f 10 10 1e 10 10 1f
46 1f 10 10 1e 10 10 10
47 0e 11 10 17 11 11 0f
48 11 11 11 1f 11 11 11
49 0e 04 04 04 04 04 0e
4a 07 02 02 02 02 12 0c
4b 11 12 14 18 14 12 11
4c 10 10 10 10 10 10 1f
4d 11 1b 15 15 11 11 11
4e 11 19 15 13 11 11 11
4f 0e 11 11 11 11 11 0e
50 1e 11 11 1e 10 10 10
51 0e 11 11 11 15 12 0d
52 1e 11 11 1e 14 12 11
53 0f 10 10 0e 01 01 1e
54 1f 04 04 04 04 04 04
55 11 11 11 11 11 11 0e
56 11 11 11 11 11 0a 04
57 11 11 11 15 15 15 0a
58 11 11 0a 04 0a 11 11
59 11 11 0a 04 04 04 04
5a 1f 01 02 04 08 10 1f
5b 0e 08 08 08 08 08 0e
5c 10 08 08 04 02 02 01
5d 0e 02 02 02 02 02 0e
5e 04 0a 11 00 00 00 00
5f 00 00 00 00 00 00 1f
60 08 04 02 00 00 00 00
61 00 00 0e 01 0f 11 0f
62 10 10 16 19 11 11 1e
63 00 00 0e 10 10 11 0e
64 01 01 0d 13 11 11 0f
65 00 00 0e 11 1f 10 0e
66 06 09 08 1c 08 08 08
67 00 0f 11 11 0f 01 0e
68 10 10 16 19 11 11 11
69 04 00 0c 04 04 04 0e
6a 02 00 06 02 02 12 0c
6b 10 10 12 14 18 14 12
6c 0c 04 04 04 04 04 0e
6d 00 00 1a 15 15 15 15
6e 00 00 16 19 11 11 11
6f 00 00 0e 11 11 11 0e
70 00 00 1e 11 1e 10 10
71 00 00 0f 11 0f 01 01
72 00 00 16 19 10 10 10
73 00 00 0f 10 0e 01 1e
74 08 08 1c 08 08 09 06
75 00 00 11 11 11 13 0d
76 00 00 11 11 11 0a 04
77 00 00 11 11 15 15 0a
78 00 00 11 0a 04 0a 11
79 00 00 11 11 0f 01 0e
7a 00 00 1f 02 04 08 1f
7b 02 04 04 08 04 04 02
7c 04 04 04 04 04 04 04
7d 08 04 04 02 04 04 08
7e 00 00 09 16 00 00 00
`.trim().split('\n').map(line => line.trim().split(/\s+/).map(hex => parseInt(hex, 16)));
const lcdFont = new Map(lcdAsciiRows.map(([code, ...rows]) => [code, [...rows, 0]]));
const lcdBlank = Object.freeze(Array(8).fill(0));

function lcdGlyph(code, glyphs) {
  if (code < 8) return glyphs[code] || lcdBlank;
  if (code === 255) return [31, 31, 31, 31, 31, 31, 31, 31];
  return lcdFont.get(code) || lcdBlank;
}

function drawLcd(canvas, data, ink) {
  const ctx = canvas.getContext('2d');
  const cellWidth = canvas.width / 20, cellHeight = canvas.height / 4;
  const pitch = Math.max(1, Math.floor(Math.min((cellWidth - 8) / 5, (cellHeight - 6) / 8)));
  const dotSize = Math.max(1, pitch - 1);
  const insetX = Math.floor((cellWidth - 5 * pitch) / 2);
  const insetY = Math.floor((cellHeight - 8 * pitch) / 2);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = ink;
  // Inactive electrodes are faintly visible even in empty character cells.
  ctx.globalAlpha = 0.075;
  for (let row = 0; row < 4; row++) for (let col = 0; col < 20; col++) {
    for (let y = 0; y < 8; y++) for (let x = 0; x < 5; x++) {
      ctx.fillRect(col * cellWidth + insetX + x * pitch, row * cellHeight + insetY + y * pitch, dotSize, dotSize);
    }
  }
  ctx.globalAlpha = 1;
  const text = data.rows.map((row, r) => row.map((code, col) => {
    const glyph = lcdGlyph(code, data.glyphs);
    for (let y = 0; y < 8; y++) for (let x = 0; x < 5; x++) {
      if ((glyph[y] || 0) & (1 << (4 - x))) {
        ctx.fillRect(col * cellWidth + insetX + x * pitch, r * cellHeight + insetY + y * pitch, dotSize, dotSize);
      }
    }
    return code < 8 ? '▧' : code === 255 ? '█' : code >= 32 && code < 127 ? String.fromCharCode(code) : ' ';
  }).join('')).join('\n');
  canvas.setAttribute('aria-label', text);
}
