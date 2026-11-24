import {heading, panel} from '../components/common/heading.js';
import {records} from '../components/common/records.js';
import {badge} from '../components/common/status.js';
import {topic} from '../constants/project.js';
import {date, esc} from '../utils/dom.js';
import {submit} from '../hooks/submit.js';

const example = [
  {number: 1205, new_number: 1207},
  {number: 1207, new_number: 1209},
  {number: 1209, new_number: 1205},
];

function movesText(items) {
  const moves = (Array.isArray(items) ? items : []).map(x=>`${x.old_number ?? x.number}→${x.new_number}`);
  return moves.length > 12 ? `${moves.slice(0, 12).join('，')} 等 ${moves.length} 项` : moves.join('，');
}

export function catalogPage(state) {
  const {catalog, orders, session} = state;
  const version = catalog ? catalog.version : '—';
  const scores = catalog ? catalog.scores : [];
  const directory = records(['曲谱编号', '谱名', '可借份数'],
    scores.map(row=>[esc(row.number), esc(row.title), esc(row.available_copies)]), '目录为空。');
  const form = session.role==='operator' ? `<form id="renumber-form">
    <input type="hidden" name="base_version" value="${esc(version)}">
    <label class="field data"><span>换号明细</span><small>JSON 数组；每项含 number（旧编号）与 new_number（新编号），基于第 ${esc(version)} 版目录</small><textarea name="items" rows="7" spellcheck="false">${esc(JSON.stringify(example, null, 2))}</textarea></label>
    <div class="actions form-actions"><button>提交换号单</button></div></form>`
    : '<p class="note">经办员可提交换号单。</p>';
  const history = records(['换号单', '基于版本', '结果', '退回原因', '换号明细', '经办', '时间'],
    (orders || []).map(row=>[esc(row.id), `第 ${esc(row.base_version)} 版`, badge(row.status),
      esc(row.reason || '—'), esc(movesText(row.items)), esc(row.actor), esc(date(row.created_at))]),
    '暂无换号记录。');
  return `${heading(topic.modules[4], `谱夹当前为第 ${esc(version)} 版目录。同一批曲谱可以互换编号或循环换号；新号撞上未参与的曲谱或同一新号分给多首曲谱，整张退回；目录一次性切换到新号，谱名和可借份数跟原曲走。`)}
    <div class="spread"><section aria-label="当前目录">${panel(`当前目录 · 第 ${esc(version)} 版`, directory)}</section>
    <aside class="brief"><h2>提交换号单</h2>${form}</aside></div>
    ${panel('换号记录', history)}`;
}

export function bindCatalog(state, api, refresh, fail) {
  submit('renumber-form', async data=>{
    let items;
    try { items = JSON.parse(data.get('items')); }
    catch { throw new Error('换号明细须为 JSON 数组。'); }
    const order = await api('/catalog/renumber', {method:'POST', data:{base_version:Number(data.get('base_version')), items}});
    await refresh();
    const message = document.getElementById('message');
    if (message) { message.textContent=`换号单 ${order.id} 已应用，目录一次性切换到第 ${order.result_version} 版。`; message.className='ok'; }
  }, fail);
}
