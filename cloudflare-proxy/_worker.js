const ORIGIN = 'https://gafarybyh3.pythonanywhere.com';

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const target = new URL(url.pathname + url.search, ORIGIN);
    if (req.method === 'GET' && url.pathname.startsWith('/static/')) {
      const cacheKey = new Request(target.toString(), { method: 'GET' });
      const hit = await caches.default.match(cacheKey);
      if (hit) return hit;
      const headers = new Headers(req.headers);
      headers.set('Host', target.host);
      headers.delete('Cookie');
      const resp = await fetch(target.toString(), { headers });
      const out = new Response(resp.body, { status: resp.status, headers: new Headers(resp.headers) });
      out.headers.set('Cache-Control', 'public, max-age=86400');
      ctx.waitUntil(caches.default.put(cacheKey, out.clone()));
      return out;
    }
    const headers = new Headers(req.headers);
    headers.set('Host', target.host);
    headers.set('X-Forwarded-Host', url.host);
    const resp = await fetch(target.toString(), {
      method: req.method,
      headers,
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : req.body,
      redirect: 'manual',
      duplex: 'half',
    });
    const out = new Headers(resp.headers);
    const loc = out.get('Location');
    if (loc) {
      try {
        const l = new URL(loc, ORIGIN);
        if (l.host === target.host) out.set('Location', l.pathname + l.search + l.hash);
      } catch {}
    }
    return new Response(resp.body, { status: resp.status, headers: out });
  }
};
