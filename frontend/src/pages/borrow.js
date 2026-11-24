import {heading, panel} from '../components/common/heading.js';
import {records} from '../components/common/records.js';
import {topic} from '../constants/project.js';
import {date, esc} from '../utils/dom.js';
import {submit} from '../hooks/submit.js';

export function borrowPage(state, identity) {
  const {slips, slipDetail, session} = state;
  const operator = session.role==='operator';
  const rows = (slips || []).map(row=>[`<a href="#borrow/${row.id}" ${row.id===identity?'aria-current="true"':''}>借阅单 ${esc(row.id)}</a>`,
    `${esc(row.range_start)} 至 ${esc(row.range_end)}`, `第 ${esc(row.catalog_version)} 版`, esc(row.actor), esc(date(row.created_at))]);
  const form = operator ? `<form id="slip-form">
    <label class="field"><span>起始曲谱编号（含）</span><input name="range_start" type="number" min="1" max="999999999" value="1204" required></label>
    <label class="field"><span>结束曲谱编号（含）</span><input name="range_end" type="number" min="1" max="999999999" value="1212" required></label>
    <div class="actions form-actions"><button>按当前目录开单</button></div></form>`
    : '<p class="note">经办员可按号段开单。</p>';
  const detail = slipDetail ? panel(`借阅单 ${esc(slipDetail.id)} · 号段 ${esc(slipDetail.range_start)} 至 ${esc(slipDetail.range_end)}`,
    `<p class="note">开单时为第 ${esc(slipDetail.catalog_version)} 版目录，当前为第 ${esc(slipDetail.current_version)} 版。系统按开单时的号段认回这些曲谱并给出现在的编号，无需逐次翻查换号记录。</p>
    ${records(['开单时编号', '现编号', '谱名', '可借份数', '号码状态'],
      slipDetail.rows.map(row=>[esc(row.old_number), esc(row.current_number), esc(row.title), esc(row.available_copies),
        row.old_number===row.current_number ? '未换号' : '已换号']),
      '该号段在开单时的目录中没有曲谱。')}`)
    : '<p class="empty">选择一张借阅单，查看号段认回结果。</p>';
  return `${heading(topic.modules[5], '按号段开单。即使之后换过几次号，打开旧借阅单仍能看到那些曲谱现在的编号。')}
    <div class="spread"><section aria-label="借阅单">${records(['借阅单', '号段', '开单时目录版本', '经办', '开单时间'], rows, '暂无借阅单。经办员可以按号段开第一张。')}</section>
    <aside class="brief"><h2>开单</h2>${form}</aside></div>
    ${detail}`;
}

export function bindBorrow(state, api, refresh, fail) {
  submit('slip-form', async data=>{
    const slip = await api('/borrow/slips', {method:'POST',
      data:{range_start:Number(data.get('range_start')), range_end:Number(data.get('range_end'))}});
    await refresh();
    const message = document.getElementById('message');
    if (message) { message.textContent=`借阅单 ${slip.id} 已开单，记录第 ${slip.catalog_version} 版目录的号段。`; message.className='ok'; }
  }, fail);
}
