// ==UserScript==
// @name         cheat-on-x exporter
// @namespace    cheat-on-x
// @version      0.1.0
// @description  浏览 x.com 时记录页面已经加载的帖子数据（曝光/赞/转/引用/回复/收藏/正文/回复区/趋势），一键导出 CSV 给 cheat-on-x 复盘用。只读页面已收到的数据：不发额外请求、不自动滚动、不上传任何东西。
// @match        https://x.com/*
// @match        https://twitter.com/*
// @run-at       document-start
// @grant        none
// @inject-into  page
// @license      MIT
// ==/UserScript==

/*
 * How it works
 * ------------
 * x.com loads timelines, post details and Explore through its own GraphQL responses.
 * This script wraps window.fetch / XMLHttpRequest so it can READ those responses after the
 * page receives them (it never alters or re-sends requests), walks the JSON for post objects,
 * and keeps the latest numbers per post in this browser's localStorage.
 *
 * Export buttons write CSV files with the canonical columns that
 * adapters/perf-data/x-csv-import understands. Everything stays on your machine.
 *
 * What you see is what gets recorded: scroll your own profile to capture your posts,
 * open a post and scroll its replies to capture replies, open Explore to capture trends.
 */
(function () {
  'use strict';

  const VERSION = '0.1.0';
  const STORE_KEY = 'cheatx.records.v1';
  const TREND_KEY = 'cheatx.trends.v1';
  const HANDLE_KEY = 'cheatx.handle';
  const MAX_RECORDS = 2500;
  const MAX_TRENDS = 300;

  const HEADER = [
    'post_id', 'url', 'author', 'created_at', 'captured_at', 'form', 'text',
    'impressions', 'likes', 'reposts', 'quotes', 'replies', 'bookmarks',
    'engagements', 'profile_visits', 'new_follows', 'link_clicks', 'detail_expands',
    'media_views', 'shares', 'has_link', 'media', 'lang', 'in_reply_to_id',
    'in_reply_to_user', 'conversation_id', 'quoted_id', 'is_note_tweet', 'is_article', 'source',
  ];
  const TREND_HEADER = ['name', 'meta', 'domain', 'url', 'captured_at'];

  // ------------------------------------------------------------ pure helpers (unit-tested)

  function toNumber(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function toIso(twitterDate) {
    if (!twitterDate) return null;
    const d = new Date(twitterDate);
    return isNaN(d.getTime()) ? null : d.toISOString();
  }

  function isStatusUrl(u) {
    return /(?:x|twitter)\.com\/[^/]+\/status\/\d+/i.test(u || '');
  }

  function parseTweet(t, capturedAt) {
    if (!t || typeof t !== 'object') return null;
    const legacy = t.legacy || {};
    const id = t.rest_id || legacy.id_str;
    if (!id || !/^\d+$/.test(String(id))) return null;
    if (legacy.retweeted_status_result) return null; // a plain repost: its inner post is recorded separately
    const user = t.core && t.core.user_results && t.core.user_results.result;
    const handle = (user && ((user.core && user.core.screen_name) || (user.legacy && user.legacy.screen_name))) || null;
    const note = t.note_tweet && t.note_tweet.note_tweet_results && t.note_tweet.note_tweet_results.result &&
      t.note_tweet.note_tweet_results.result.text;
    const mediaList = ((legacy.extended_entities && legacy.extended_entities.media) ||
      (legacy.entities && legacy.entities.media) || []).map(function (m) { return m.type; });
    const cardName = t.card && t.card.legacy && t.card.legacy.name;
    if (cardName && /^poll/i.test(cardName)) mediaList.push('poll');
    const urls = ((legacy.entities && legacy.entities.urls) || [])
      .map(function (u) { return u.expanded_url || u.url || ''; })
      .filter(function (u) { return u && !isStatusUrl(u); });
    const views = t.views && t.views.count !== undefined ? toNumber(t.views.count) : null;
    return {
      post_id: String(id),
      url: 'https://x.com/' + (handle || 'i/web') + '/status/' + id,
      author: handle,
      created_at: toIso(legacy.created_at),
      captured_at: capturedAt,
      form: '',
      text: note || legacy.full_text || '',
      impressions: views,
      likes: toNumber(legacy.favorite_count),
      reposts: toNumber(legacy.retweet_count),
      quotes: toNumber(legacy.quote_count),
      replies: toNumber(legacy.reply_count),
      bookmarks: toNumber(legacy.bookmark_count),
      engagements: null, profile_visits: null, new_follows: null, link_clicks: null,
      detail_expands: null, media_views: null, shares: null,
      has_link: urls.length > 0,
      media: Array.from(new Set(mediaList)).join('|'),
      lang: legacy.lang || null,
      in_reply_to_id: legacy.in_reply_to_status_id_str || null,
      in_reply_to_user: legacy.in_reply_to_screen_name || null,
      conversation_id: legacy.conversation_id_str || null,
      quoted_id: legacy.quoted_status_id_str || null,
      is_note_tweet: !!note,
      is_article: !!t.article,
      source: 'userscript',
    };
  }

  /** Walk any GraphQL JSON and return every post object found (deduped by id). */
  function extractTweets(json, capturedAt) {
    capturedAt = capturedAt || new Date().toISOString();
    const out = new Map();
    const seen = new Set();
    (function walk(node, depth) {
      if (!node || typeof node !== 'object' || depth > 60 || seen.has(node)) return;
      seen.add(node);
      if (Array.isArray(node)) { node.forEach(function (n) { walk(n, depth + 1); }); return; }
      let candidate = null;
      if (node.__typename === 'TweetWithVisibilityResults' && node.tweet) candidate = node.tweet;
      else if (node.__typename === 'Tweet' || (node.rest_id && node.legacy && node.legacy.full_text !== undefined)) candidate = node;
      if (candidate) {
        const rec = parseTweet(candidate, capturedAt);
        // the same post can appear several times in one response (e.g. as a quoted copy that
        // lacks some fields) — merge instead of overwrite
        if (rec) out.set(rec.post_id, mergeRecord(out.get(rec.post_id), rec));
      }
      for (const k in node) {
        if (Object.prototype.hasOwnProperty.call(node, k)) walk(node[k], depth + 1);
      }
    })(json, 0);
    return Array.from(out.values());
  }

  /** Explore / trends modules → [{name, meta, domain, url, captured_at}] */
  function extractTrends(json, capturedAt) {
    capturedAt = capturedAt || new Date().toISOString();
    const out = new Map();
    const seen = new Set();
    (function walk(node, depth) {
      if (!node || typeof node !== 'object' || depth > 60 || seen.has(node)) return;
      seen.add(node);
      if (Array.isArray(node)) { node.forEach(function (n) { walk(n, depth + 1); }); return; }
      let name = null; let meta = null; let domain = null;
      if (node.__typename === 'TimelineTrend' && node.name) {
        name = node.name;
        meta = node.trend_metadata && node.trend_metadata.meta_description;
        domain = node.trend_metadata && node.trend_metadata.domain_context;
      } else if (node.trend && typeof node.trend === 'object' && node.trend.name) {
        name = node.trend.name;
        const md = node.trend.trendMetadata || node.trend.trend_metadata || {};
        meta = md.metaDescription || md.meta_description || null;
        domain = md.domainContext || md.domain_context || null;
      }
      if (name) {
        out.set(name, {
          name: name, meta: meta || null, domain: domain || null,
          url: 'https://x.com/search?q=' + encodeURIComponent(name), captured_at: capturedAt,
        });
      }
      for (const k in node) {
        if (Object.prototype.hasOwnProperty.call(node, k)) walk(node[k], depth + 1);
      }
    })(json, 0);
    return Array.from(out.values());
  }

  // Post analytics page (experimental): label → number pairs from the visible page text.
  // Likes / reposts / replies / bookmarks are deliberately absent: GraphQL already gives exact
  // values, and those words appear all over the page (buttons, headings) → false matches.
  // Bare "关注" / "Follow" are absent for the same reason.
  const ANALYTICS_LABELS = {
    impressions: ['impressions', '展示次数', '展示量', '曝光次数'],
    engagements: ['engagements', '互动次数'],
    detail_expands: ['detail expands', '详细信息展开', '展开详情'],
    profile_visits: ['profile visits', '个人资料访问', '个人资料访问次数'],
    new_follows: ['new followers', 'new follows', '新关注者', '新增关注'],
    link_clicks: ['link clicks', 'url clicks', '链接点击', '链接点击次数'],
    media_views: ['media views', '媒体浏览', '媒体浏览量'],
    shares: ['shares', '分享次数'],
  };

  function parseCount(s) {
    if (s === null || s === undefined) return null;
    const m = String(s).replace(/[,\s  ]/g, '').match(/^(\d+(?:\.\d+)?)([KkMm万亿]?)$/);
    if (!m) return null;
    const mult = { k: 1e3, K: 1e3, m: 1e6, M: 1e6, '万': 1e4, '亿': 1e8 }[m[2]] || 1;
    return Math.round(parseFloat(m[1]) * mult);
  }

  function parseAnalyticsText(text) {
    const lines = String(text || '').split(/\n+/).map(function (l) { return l.trim(); }).filter(Boolean);
    const result = {};
    for (let i = 0; i < lines.length; i++) {
      const low = lines[i].toLowerCase();
      for (const field in ANALYTICS_LABELS) {
        if (result[field] !== undefined) continue;
        if (ANALYTICS_LABELS[field].indexOf(low) === -1) continue;
        // value is either on the next line or the previous line (layouts differ)
        const next = parseCount(lines[i + 1]);
        const prev = i > 0 ? parseCount(lines[i - 1]) : null;
        const v = next !== null ? next : prev;
        if (v !== null) result[field] = v;
      }
    }
    return result;
  }

  function csvCell(v) {
    if (v === null || v === undefined) return '';
    const s = typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function toCSV(rows, header) {
    const lines = [header.join(',')];
    rows.forEach(function (r) { lines.push(header.map(function (h) { return csvCell(r[h]); }).join(',')); });
    return '﻿' + lines.join('\r\n') + '\r\n';
  }

  /** Records for "my posts + replies/quotes under them". */
  function selectMine(records, handle) {
    const h = (handle || '').replace(/^@/, '').toLowerCase();
    if (!h) return records;
    const mine = records.filter(function (r) { return (r.author || '').toLowerCase() === h; });
    const ids = new Set(mine.map(function (r) { return r.post_id; }));
    const related = records.filter(function (r) {
      return !ids.has(r.post_id) && (ids.has(r.conversation_id) || ids.has(r.in_reply_to_id) || ids.has(r.quoted_id));
    });
    return mine.concat(related);
  }

  /** Merge a fresh capture into an existing record: newer non-null values win. */
  function mergeRecord(old, fresh) {
    if (!old) return fresh;
    const m = Object.assign({}, old);
    for (const k in fresh) {
      if (fresh[k] !== null && fresh[k] !== undefined && fresh[k] !== '') m[k] = fresh[k];
    }
    return m;
  }

  // ------------------------------------------------------------ browser side

  function main() {
    let records = {};
    let trends = {};
    try { records = JSON.parse(localStorage.getItem(STORE_KEY) || '{}'); } catch (e) { records = {}; }
    try { trends = JSON.parse(localStorage.getItem(TREND_KEY) || '{}'); } catch (e) { trends = {}; }

    let saveTimer = null;
    function scheduleSave() {
      if (saveTimer) return;
      saveTimer = setTimeout(function () {
        saveTimer = null;
        const ids = Object.keys(records);
        if (ids.length > MAX_RECORDS) {
          ids.sort(function (a, b) { return (records[a].captured_at || '').localeCompare(records[b].captured_at || ''); });
          ids.slice(0, ids.length - MAX_RECORDS).forEach(function (id) { delete records[id]; });
        }
        const tnames = Object.keys(trends);
        if (tnames.length > MAX_TRENDS) {
          tnames.sort(function (a, b) { return (trends[a].captured_at || '').localeCompare(trends[b].captured_at || ''); });
          tnames.slice(0, tnames.length - MAX_TRENDS).forEach(function (n) { delete trends[n]; });
        }
        try {
          localStorage.setItem(STORE_KEY, JSON.stringify(records));
          localStorage.setItem(TREND_KEY, JSON.stringify(trends));
        } catch (e) { console.warn('[cheat-on-x] localStorage full — export and clear', e); }
        renderPanel();
      }, 1500);
    }

    function ingest(json) {
      const now = new Date().toISOString();
      extractTweets(json, now).forEach(function (r) { records[r.post_id] = mergeRecord(records[r.post_id], r); });
      extractTrends(json, now).forEach(function (t) { trends[t.name] = t; });
      scheduleSave();
    }

    function isApi(url) { return /\/graphql\/|\/i\/api\//.test(String(url || '')); }

    // Read-only taps on responses the page already requested.
    const origFetch = window.fetch;
    if (origFetch) {
      window.fetch = function () {
        const args = arguments;
        return origFetch.apply(this, args).then(function (res) {
          try {
            const req = args[0];
            const url = typeof req === 'string' ? req : (req && req.url);
            if (isApi(url)) res.clone().json().then(ingest).catch(function () {});
          } catch (e) { /* never break the page */ }
          return res;
        });
      };
    }
    const XHR = window.XMLHttpRequest && window.XMLHttpRequest.prototype;
    if (XHR) {
      const origOpen = XHR.open;
      const origSend = XHR.send;
      XHR.open = function (method, url) { this.__cheatxUrl = url; return origOpen.apply(this, arguments); };
      XHR.send = function () {
        if (isApi(this.__cheatxUrl)) {
          this.addEventListener('load', function () {
            try {
              if (this.responseType === 'json') ingest(this.response);
              else if (!this.responseType || this.responseType === 'text') ingest(JSON.parse(this.responseText));
            } catch (e) { /* ignore non-JSON */ }
          });
        }
        return origSend.apply(this, arguments);
      };
    }

    // ---------------- UI
    let panel = null;
    let collapsed = localStorage.getItem('cheatx.collapsed') === '1';

    function download(name, text) {
      const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    }

    function stamp() {
      const d = new Date();
      const p = function (n) { return String(n).padStart(2, '0'); };
      return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '-' + p(d.getHours()) + p(d.getMinutes());
    }

    function currentStatusId() {
      const m = location.pathname.match(/\/status\/(\d+)/);
      return m ? m[1] : null;
    }

    function readAnalytics() {
      const id = currentStatusId();
      if (!id) { alert('先打开一条帖子的分析页（帖子 → 查看帖子分析 / View post analytics）'); return; }
      const got = parseAnalyticsText(document.body.innerText);
      const n = Object.keys(got).length;
      if (!n) { alert('这一页没认出分析数据的标签。界面语言或版式可能变了——这部分是实验功能，复盘时手动粘贴即可。'); return; }
      records[id] = mergeRecord(records[id] || { post_id: id, url: 'https://x.com/i/web/status/' + id, source: 'userscript' },
        Object.assign({ captured_at: new Date().toISOString() }, got));
      scheduleSave();
      alert('已读取 ' + n + ' 项：' + Object.keys(got).join(', '));
    }

    function btn(label, onClick) {
      const b = document.createElement('button');
      b.textContent = label;
      b.style.cssText = 'display:block;width:100%;margin:4px 0;padding:4px 8px;border:1px solid #536471;' +
        'border-radius:6px;background:transparent;color:inherit;font:12px system-ui;cursor:pointer;text-align:left';
      b.addEventListener('click', onClick);
      return b;
    }

    function renderPanel() {
      if (!document.body) return;
      if (!panel) {
        panel = document.createElement('div');
        panel.id = 'cheatx-panel';
        panel.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:2147483647;max-width:230px;' +
          'padding:8px 10px;border-radius:10px;background:rgba(15,20,25,.92);color:#e7e9ea;' +
          'font:12px system-ui;box-shadow:0 2px 12px rgba(0,0,0,.35)';
        document.body.appendChild(panel);
      }
      const nPosts = Object.keys(records).length;
      const nTrends = Object.keys(trends).length;
      const handle = localStorage.getItem(HANDLE_KEY) || '';
      while (panel.firstChild) panel.removeChild(panel.firstChild); // no innerHTML (Trusted Types safe)
      const title = document.createElement('div');
      title.style.cssText = 'cursor:pointer;font-weight:600';
      title.textContent = 'cheat-on-x · ' + nPosts + ' 帖 · ' + nTrends + ' 趋势 ' + (collapsed ? '▸' : '▾');
      title.addEventListener('click', function () {
        collapsed = !collapsed;
        localStorage.setItem('cheatx.collapsed', collapsed ? '1' : '0');
        renderPanel();
      });
      panel.appendChild(title);
      if (collapsed) return;
      const info = document.createElement('div');
      info.style.cssText = 'opacity:.75;margin:4px 0';
      info.textContent = handle ? '我的 handle：@' + handle : '还没设置我的 handle';
      panel.appendChild(info);
      panel.appendChild(btn('导出：我的帖子 + 回复/引用', function () {
        if (!handle) { alert('先点"设置我的 handle"'); return; }
        const rows = selectMine(Object.values(records), handle);
        download('cheatx-mine-' + stamp() + '.csv', toCSV(rows, HEADER));
      }));
      panel.appendChild(btn('导出：全部已记录帖子（含对标账号）', function () {
        download('cheatx-posts-' + stamp() + '.csv', toCSV(Object.values(records), HEADER));
      }));
      panel.appendChild(btn('导出：趋势', function () {
        download('cheatx-trends-' + stamp() + '.csv', toCSV(Object.values(trends), TREND_HEADER));
      }));
      panel.appendChild(btn('读取本页分析数据（实验）', readAnalytics));
      panel.appendChild(btn('设置我的 handle', function () {
        const v = prompt('你的 X handle（不带 @）', handle);
        if (v !== null) { localStorage.setItem(HANDLE_KEY, v.replace(/^@/, '').trim()); renderPanel(); }
      }));
      panel.appendChild(btn('清空记录', function () {
        if (!confirm('清空本浏览器里记录的所有帖子和趋势？（已导出的文件不受影响）')) return;
        records = {}; trends = {};
        localStorage.removeItem(STORE_KEY); localStorage.removeItem(TREND_KEY);
        renderPanel();
      }));
      const foot = document.createElement('div');
      foot.style.cssText = 'opacity:.5;margin-top:4px';
      foot.textContent = 'v' + VERSION + ' · 数据只存在本浏览器';
      panel.appendChild(foot);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', renderPanel);
    else renderPanel();
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      HEADER: HEADER, TREND_HEADER: TREND_HEADER, parseTweet: parseTweet, extractTweets: extractTweets,
      extractTrends: extractTrends, parseAnalyticsText: parseAnalyticsText, parseCount: parseCount,
      toCSV: toCSV, selectMine: selectMine, mergeRecord: mergeRecord,
    };
  } else {
    main();
  }
})();
