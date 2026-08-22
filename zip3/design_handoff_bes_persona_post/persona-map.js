// <persona-map> — d3-rendered Scotland outline with a constituency dot.
// Requires d3 + topojson-client already loaded (pinned tags in the page helmet).
(function () {
  const DATA_URL = 'https://cdn.jsdelivr.net/gh/martinjc/UK-GeoJSON@master/json/electoral/sco/topo_eer.json';
  let dataPromise = null;
  class PersonaMap extends HTMLElement {
    static observedAttributes = ['shape', 'fill', 'dot', 'lon', 'lat', 'width', 'height'];
    connectedCallback() { this.render(); }
    attributeChangedCallback() { if (this.isConnected) this.render(); }
    async render() {
      const w = +this.getAttribute('width') || 420;
      const h = +this.getAttribute('height') || 640;
      const lon = +this.getAttribute('lon') || -4.2518;
      const lat = +this.getAttribute('lat') || 55.8642;
      const label = this.getAttribute('label') || '';
      const fill = this.getAttribute('fill') || '#84a883';
      const stroke = this.getAttribute('stroke') || '#4c6b4b';
      const dot = this.getAttribute('dot') || '#ec3013';
      const ink = this.getAttribute('ink') || '#201e1d';
      this.style.display = 'block';
      this.style.width = w + 'px';
      this.style.height = h + 'px';
      try {
        dataPromise = dataPromise || fetch(DATA_URL).then(r => {
          if (!r.ok) throw new Error('map data ' + r.status);
          return r.json();
        });
        const topo = await dataPromise;
        const key = Object.keys(topo.objects)[0];
        const fc = topojson.feature(topo, topo.objects[key]);
        const proj = d3.geoMercator().fitExtent([[8, 8], [w - 8, h - 8]], fc);
        const [x, y] = proj([lon, lat]);
        // slight simplification: drop projected points closer than `tol` px, cull tiny islets
        const tol = +this.getAttribute('simplify') || 1.4;
        const polys = [];
        for (const f of (fc.features || [fc])) {
          const g = f.geometry; if (!g) continue;
          if (g.type === 'Polygon') polys.push(g.coordinates);
          else if (g.type === 'MultiPolygon') g.coordinates.forEach(p => polys.push(p));
        }
        let dStr = '';
        for (const poly of polys) {
          const pts = [];
          for (const c of poly[0]) {
            const p = proj(c); if (!p) continue;
            const last = pts[pts.length - 1];
            if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) >= tol) pts.push(p);
          }
          if (pts.length < 4) continue;
          let minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
          for (const p of pts) { minx = Math.min(minx, p[0]); maxx = Math.max(maxx, p[0]); miny = Math.min(miny, p[1]); maxy = Math.max(maxy, p[1]); }
          if ((maxx - minx) + (maxy - miny) < 7) continue;
          dStr += 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('L') + 'Z';
        }
        const svg = d3.create('svg').attr('viewBox', `0 0 ${w} ${h}`).attr('width', w).attr('height', h);
        svg.append('path').attr('d', dStr).attr('fill', fill).attr('stroke', stroke).attr('stroke-width', 1.25).attr('stroke-linejoin', 'round');
        if (this.getAttribute('shape') === 'square') {
          svg.append('rect').attr('x', x - 11).attr('y', y - 11).attr('width', 22).attr('height', 22).attr('fill', dot).attr('stroke', '#ffffff').attr('stroke-width', 3);
        } else {
          svg.append('circle').attr('cx', x).attr('cy', y).attr('r', 11).attr('fill', dot).attr('stroke', '#ffffff').attr('stroke-width', 3);
        }
        this.replaceChildren(svg.node());
      } catch (e) {
        this.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:flex-end;padding:12px;box-sizing:border-box;border:2px solid ' + stroke + ';color:' + stroke + ';font:600 13px Archivo,sans-serif">MAP UNAVAILABLE</div>';
      }
    }
  }
  if (!customElements.get('persona-map')) customElements.define('persona-map', PersonaMap);
})();
