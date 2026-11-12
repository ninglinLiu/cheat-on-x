// Unit tests for the userscript's pure functions. Synthetic GraphQL shapes, no network.
// Run: node --test userscripts/test/
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const X = require('../cheatx-exporter.user.js');

function tweet(id, opts) {
  opts = opts || {};
  const t = {
    __typename: 'Tweet',
    rest_id: id,
    core: { user_results: { result: { __typename: 'User', core: { screen_name: opts.handle || 'me' } } } },
    views: { count: opts.views !== undefined ? String(opts.views) : '2130', state: 'EnabledWithCount' },
    legacy: {
      id_str: id,
      created_at: 'Mon Nov 10 13:00:00 +0000 2026',
      full_text: opts.text || '我用 AI 写作半年后删掉的 7 个提示词',
      favorite_count: opts.likes !== undefined ? opts.likes : 54,
      retweet_count: 9, quote_count: 3, reply_count: 17, bookmark_count: 31,
      lang: 'zh', conversation_id_str: opts.conversation || id,
      in_reply_to_status_id_str: opts.replyTo, in_reply_to_screen_name: opts.replyToUser,
      quoted_status_id_str: opts.quoted,
      entities: { urls: opts.urls || [] },
      extended_entities: opts.media ? { media: opts.media.map(function (t) { return { type: t }; }) } : undefined,
    },
  };
  if (opts.note) t.note_tweet = { note_tweet_results: { result: { text: opts.note } } };
  if (opts.legacyHandle) {
    t.core.user_results.result = { legacy: { screen_name: opts.legacyHandle } };
  }
  return t;
}

// Shape modeled on a TweetDetail response: instructions → entries → content → itemContent → tweet_results
function tweetDetail() {
  return {
    data: { threaded_conversation_with_injections_v2: { instructions: [{
      type: 'TimelineAddEntries',
      entries: [
        { entryId: 'tweet-1001', content: { itemContent: { tweet_results: { result: tweet('1001', { media: ['photo'] }) } } } },
        { entryId: 'conversationthread-1', content: { items: [
          { item: { itemContent: { tweet_results: { result: tweet('2001', { handle: 'alice', likes: 12, replyTo: '1001', replyToUser: 'me', conversation: '1001', text: '还可以加一个，先列反例' }) } } } },
          { item: { itemContent: { tweet_results: { result: { __typename: 'TweetWithVisibilityResults', tweet: tweet('2002', { handle: 'bob', likes: 40, replyTo: '1001', replyToUser: 'me', conversation: '1001', text: '求模板, "完整版"' }) } } } } },
        ] } },
        { entryId: 'tweet-3001', content: { itemContent: { tweet_results: { result: Object.assign(tweet('3001', { handle: 'carol', quoted: '1001', text: '值得收藏', urls: [{ expanded_url: 'https://x.com/me/status/1001' }] }), {
          quoted_status_result: { result: tweet('1001', { views: 2200 }) },
        }) } } } },
        { entryId: 'tweet-4001', content: { itemContent: { tweet_results: { result: tweet('4001', { note: '很长的长帖正文'.repeat(40), urls: [{ expanded_url: 'https://example.com/a' }] }) } } } },
      ],
    }] } },
  };
}

test('extractTweets finds every post object, including visibility wrappers and quoted posts', function () {
  const recs = X.extractTweets(tweetDetail(), '2026-11-12T13:30:00.000Z');
  const ids = recs.map(function (r) { return r.post_id; }).sort();
  assert.deepEqual(ids, ['1001', '2001', '2002', '3001', '4001']);
});

test('parseTweet maps GraphQL fields to canonical columns', function () {
  const recs = X.extractTweets(tweetDetail(), '2026-11-12T13:30:00.000Z');
  const byId = Object.fromEntries(recs.map(function (r) { return [r.post_id, r]; }));
  const head = byId['1001'];
  assert.equal(head.author, 'me');
  assert.equal(head.created_at, '2026-11-10T13:00:00.000Z');
  assert.equal(head.likes, 54);
  assert.equal(head.bookmarks, 31);
  assert.equal(head.media, 'photo');
  assert.equal(head.has_link, false);
  assert.equal(byId['2002'].in_reply_to_id, '1001');
  assert.equal(byId['2002'].author, 'bob');
  assert.equal(byId['3001'].quoted_id, '1001');
  assert.equal(byId['3001'].has_link, false, 'a link to another post is not an external link');
  assert.equal(byId['4001'].is_note_tweet, true);
  assert.equal(byId['4001'].has_link, true);
  assert.ok(byId['4001'].text.startsWith('很长的长帖正文'));
});

test('quoted copy of a post seen later carries its own numbers (last write wins inside one response)', function () {
  const recs = X.extractTweets(tweetDetail(), 't');
  const head = recs.find(function (r) { return r.post_id === '1001'; });
  assert.ok(head.impressions === 2130 || head.impressions === 2200);
});

test('legacy user shape still yields the handle', function () {
  const r = X.parseTweet(tweet('5', { legacyHandle: 'olduser' }), 't');
  assert.equal(r.author, 'olduser');
});

test('plain reposts are skipped (their inner post is recorded on its own)', function () {
  const rt = tweet('9', {});
  rt.legacy.retweeted_status_result = { result: tweet('10', {}) };
  const recs = X.extractTweets({ a: rt }, 't');
  assert.deepEqual(recs.map(function (r) { return r.post_id; }), ['10']);
});

test('extractTrends handles TimelineTrend and older trend shapes', function () {
  const json = { a: [
    { __typename: 'TimelineTrend', name: 'OpenModel', trend_metadata: { meta_description: '12.3K posts', domain_context: 'Technology · Trending' } },
    { trend: { name: '#独立开发', trendMetadata: { metaDescription: '5,210 posts', domainContext: 'Trending in China' } } },
  ] };
  const t = X.extractTrends(json, '2026-11-12T02:00:00Z');
  assert.equal(t.length, 2);
  assert.equal(t[0].meta, '12.3K posts');
  assert.equal(t[1].url, 'https://x.com/search?q=' + encodeURIComponent('#独立开发'));
});

test('parseAnalyticsText reads label/value pairs in either order, English and Chinese', function () {
  const en = 'Post analytics\nImpressions\n2,130\nEngagements\n114\nDetail expands\n41\nProfile visits\n38\nNew follows\n6\nLink clicks\n0';
  assert.deepEqual(X.parseAnalyticsText(en),
    { impressions: 2130, engagements: 114, detail_expands: 41, profile_visits: 38, new_follows: 6, link_clicks: 0 });
  const zh = '帖子分析\n2.1万\n展示次数\n个人资料访问\n38\n新关注者\n6';
  assert.deepEqual(X.parseAnalyticsText(zh), { impressions: 21000, profile_visits: 38, new_follows: 6 });
  assert.deepEqual(X.parseAnalyticsText('关注\n120\n回复\n3'), {});
});

test('toCSV escapes quotes, commas and newlines and starts with a BOM', function () {
  const csv = X.toCSV([{ post_id: '1', text: 'a, "b"\nc', has_link: false }], ['post_id', 'text', 'has_link']);
  assert.ok(csv.startsWith('﻿post_id,text,has_link\r\n'));
  assert.ok(csv.includes('"a, ""b""\nc"'));
  assert.ok(csv.includes(',false'));
});

test('selectMine keeps my posts plus replies and quotes under them', function () {
  const recs = X.extractTweets(tweetDetail(), 't');
  const mine = X.selectMine(recs, '@Me');
  assert.deepEqual(mine.map(function (r) { return r.post_id; }).sort(), ['1001', '2001', '2002', '3001', '4001']);
  const other = X.selectMine(recs.concat([X.parseTweet(tweet('8', { handle: 'zed' }), 't')]), 'me');
  assert.ok(!other.some(function (r) { return r.post_id === '8'; }));
});

test('mergeRecord keeps analytics fields when a later GraphQL capture lacks them', function () {
  const m = X.mergeRecord({ post_id: '1', profile_visits: 38, impressions: 800 }, { post_id: '1', profile_visits: null, impressions: 2130 });
  assert.equal(m.profile_visits, 38);
  assert.equal(m.impressions, 2130);
});

test('exported CSV is readable by x-csv-import (cross-language contract)', function (t) {
  const py = ['python3', 'python'].find(function (bin) {
    return spawnSync(bin, ['--version']).status === 0;
  });
  if (!py) { t.skip('python not available'); return; }
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cheatx-'));
  const csvPath = path.join(dir, 'mine.csv');
  fs.writeFileSync(csvPath, X.toCSV(X.selectMine(X.extractTweets(tweetDetail(), '2026-11-12T13:30:00.000Z'), 'me'), X.HEADER));
  const importer = path.join(__dirname, '..', '..', 'adapters', 'perf-data', 'x-csv-import', 'import_csv.py');
  const out = path.join(dir, 'post');
  const r = spawnSync(py, [importer, 'post', csvPath, '--id', '1001', '--out', out], { encoding: 'utf-8' });
  assert.equal(r.status, 0, r.stderr);
  const summary = JSON.parse(r.stdout);
  assert.equal(summary.replies_captured, 2);
  assert.equal(summary.quotes_captured, 1);
  assert.equal(summary.form, 'single');
  const md = fs.readFileSync(path.join(out, 'report.md'), 'utf-8');
  assert.ok(md.includes('求模板, "完整版"'));
  fs.rmSync(dir, { recursive: true, force: true });
});
