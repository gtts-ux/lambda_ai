'use strict';
const $=s=>document.querySelector(s);
const icons={
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',plus:'<path d="M12 5v14M5 12h14"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  archive:'<path d="M4 8h16v12H4zM3 4h18v4H3zM9 12h6"/>',layers:'<path d="m12 3 10 6-10 6L2 9zM3 13l9 5 9-5M3 17l9 5 9-5"/>',
  settings:'<path d="m9.5 4 .7-2h3.6l.7 2 2 .9 2.1-.3 1.8 3.1-1.3 1.6.2 2.2 1.3 1.8-1.8 3.1-2.1-.3-2 .9-.7 2h-3.6l-.7-2-2-.9-2.1.3-1.8-3.1 1.3-1.8-.2-2.2-1.1-1.6 1.8-3.1 2.1.3z" transform="translate(0 1)"/><circle cx="12" cy="11.5" r="3"/>',
  panel:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  message:'<path d="M21 11a8 8 0 0 1-8 8H7l-5 3 2-6a8 8 0 0 1-1-4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  spark:'<path d="m12 2 2.7 7.3L22 12l-7.3 2.7L12 22l-2.7-7.3L2 12l7.3-2.7z"/>',orbit:'<circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="11" ry="5" transform="rotate(-35 12 12)"/>',
  chevron:'<path d="m7 9 5 5 5-5"/>',up:'<path d="M12 19V5m-6 6 6-6 6 6"/>',down:'<path d="M12 5v14m-6-6 6 6 6-6"/>',close:'<path d="m6 6 12 12M18 6 6 18"/>',
  palette:'<circle cx="12" cy="12" r="9"/><path d="M14 21c-4 0-1-6 3-6h3"/><circle cx="8" cy="9" r=".7"/><circle cx="12" cy="6" r=".7"/><circle cx="16" cy="9" r=".7"/><circle cx="6" cy="13" r=".7"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M15 8V4H4v11h4"/>',
  refresh:'<path d="M20 7v5h-5M4 17v-5h5M19 11a7 7 0 0 0-12-5L4 9m16 6-3 3a7 7 0 0 1-12-5"/>',
  pin:'<path d="m9 3 12 12-3 1-3-3-6 2-3-3 2-6zM8 15l-5 6"/>',edit:'<path d="m15 4 5 5L8 21H3v-5zM12 7l5 5"/>',stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>',check:'<path d="m5 12 4 4L19 6"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>'
};
const icon=name=>`<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.message}</svg>`;
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=value=>new Intl.NumberFormat('en-US').format(value||0);
const pretty=name=>String(name||'Lambda').replace(/^lambda\s*/i,'').replace(/\b[a-z]/g,s=>s.toUpperCase());
const size=bytes=>`${((bytes||0)/1048576).toFixed(1)} MB`;
const command=window.lambda.platform==='darwin'?'⌘':'Ctrl';
const familyNames={mercury:'Mercury',venus:'Venus',code:'Code',terra:'Terra',other:'Local models'};
const familyCopy={mercury:'Compact English models for simple conversations.',venus:'Conversation models for questions and short exchanges.',code:'Experimental Python and JavaScript assistance.',terra:'Experimental English conversation models.',other:'A model installed on this device.'};
let desktopInfo={version:'1.1.3'},updateResult=null,checkingUpdates=false,applicationUpdate=null,deleteId=null;
let S=null,tab='appearance',modelFilter='all',archived=false,query='',searchTimer,toastTimer,renameId=null,stream=null,lastMessages='',popoverAnchor=null;
const media=matchMedia('(prefers-color-scheme: dark)');
function decorate(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}
function toast(message,undo){
  const node=$('#toast');node.textContent=message;node.hidden=false;clearTimeout(toastTimer);
  if(undo){const b=document.createElement('button');b.textContent='Undo';b.onclick=()=>{undo();node.hidden=true;};node.append(b);}
  toastTimer=setTimeout(()=>{node.hidden=true;},undo?7000:4200);
}
async function act(method,params={}){
  try{const value=await window.lambda.request(method,params);if(value?.chat)applyState(value);return value;}
  catch(error){toast(error.message);return null;}
}
function applyAppearance(){
  if(!S)return;
  const p=S.preferences;const html=document.documentElement;
  html.dataset.theme=p.theme==='system'?(media.matches?'dark':'light'):p.theme;
  html.dataset.accent=p.accent;html.dataset.density=p.density;html.style.setProperty('--body-size',`${p.fontSize}px`);
}
media.addEventListener('change',applyAppearance);
function resetText(){
  if(!S?.quota.resets_at)return 'Starts with your first message';
  const seconds=Math.max(0,Math.ceil((Date.parse(S.quota.resets_at)-Date.now())/1000));
  return `${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}m`;
}
function usagePercent(){return S?Math.max(0,Math.min(100,S.quota.remaining/S.quota.allowance*100)):100;}
function liveUsage(){
  if(!S)return;
  document.querySelectorAll('[data-reset-in]').forEach(el=>{el.textContent=resetText();});
  document.querySelectorAll('[data-remaining]').forEach(el=>{el.textContent=number(S.quota.remaining);});
  document.querySelectorAll('[data-usage-fill]').forEach(el=>{el.style.width=usagePercent()+'%';});
  document.querySelectorAll('[data-percent]').forEach(el=>{el.textContent=usagePercent().toFixed(1)+'% remaining';});
}
function applyState(next){
  if(S&&next.revision<S.revision)return;
  S=next;applyAppearance();
  $('#profile-name').textContent=S.preferences.displayName;
  $('#profile-avatar').textContent=S.preferences.displayName.charAt(0).toUpperCase();
  $('#sidebar-allowance').textContent=`${Math.floor(usagePercent())}% of limit available`;
  $('#chat-title').textContent=S.chat.title;
  $('#selected-model').textContent=pretty(S.chat.modelName);
  $('#chat-notice').textContent=S.chat.notice||'';$('#chat-notice').hidden=!S.chat.notice;
  if(!query&&!archived)renderChats(S.chats);else searchChats();
  const fingerprint=JSON.stringify([S.chat.id,S.chat.messages]);
  if(fingerprint!==lastMessages){lastMessages=fingerprint;renderMessages();}
  if(!S.generating){stream=null;$('#streaming-message')?.remove();$('#generation-status').textContent='';}
  updateComposer();liveUsage();
}
function renderChats(rows){
  $('#chat-list-label').textContent=archived?'ARCHIVED CHATS':'YOUR CHATS';
  $('#archive-view').title=archived?'Show all chats':'Show archived chats';
  const root=$('#chat-list');root.replaceChildren();
  if(!rows.length){root.innerHTML=`<div class="no-chats">${query?'No matching conversations.':archived?'No archived conversations.':'Your next conversation<br>starts right here.'}</div>`;return;}
  for(const row of rows){
    const item=document.createElement('div');item.className='chat-item'+(S?.chat.id===row.id?' active':'');item.setAttribute('role','listitem');
    item.innerHTML=`<button class="chat-open" title="${esc(row.title)}">${icon('message')}<span class="chat-name">${esc(row.title)}</span>${row.pinned?'<span class="pin-dot">•</span>':''}</button><button class="chat-more icon-button tiny" aria-label="Options for ${esc(row.title)}" title="Chat options">${icon('more')}</button><button class="chat-delete icon-button tiny" aria-label="Delete ${esc(row.title)}" title="Delete conversation">${icon('trash')}</button>`;
    item.querySelector('.chat-open').onclick=async()=>{closePopover();if(archived){await act('restore_chat',{id:row.id});archived=false;}await act('open_chat',{id:row.id});$('#message-input').focus();};
    item.querySelector('.chat-delete').onclick=()=>confirmDelete(row);
    item.querySelector('.chat-more').onclick=e=>{e.stopPropagation();chatMenu(e.currentTarget,row);};root.append(item);
  }
}
async function searchChats(){
  const currentQuery=query,currentArchived=archived;
  const rows=await act('list_chats',{query:currentQuery,archived:currentArchived});
  if(rows&&query===currentQuery&&archived===currentArchived)renderChats(rows);
}
function richText(node,text){
  node.innerHTML=DOMPurify.sanitize(marked.parse(text||'',{breaks:true,gfm:true}),{FORBID_TAGS:['img','iframe','style','script','form','input','video','audio']});
  node.querySelectorAll('pre>code').forEach(code=>{
    const language=(code.className.match(/language-([\w-]+)/)||[])[1]||'text';
    if(Prism.languages[language])Prism.highlightElement(code);
    const pre=code.parentElement;const label=document.createElement('span');label.className='code-label';label.textContent=language;pre.prepend(label);
    const button=document.createElement('button');button.className='code-copy';button.textContent='Copy code';button.onclick=()=>copy(code.textContent,button);pre.append(button);
  });
  node.querySelectorAll('a[href]').forEach(link=>link.addEventListener('click',e=>{e.preventDefault();window.lambda.openExternal(link.href).catch(error=>toast(error.message));}));
}
async function copy(text,button){try{await navigator.clipboard.writeText(text);if(button){const original=button.innerHTML;button.textContent='Copied';setTimeout(()=>{button.innerHTML=original;},1300);}else toast('Copied to clipboard.');}catch{toast('Could not access the clipboard. Select the text and copy it.');}}
function modelLabel(identifier){return pretty(S.models.find(m=>m.id===identifier)?.name||S.chat.modelName);}
function renderMessages(){
  const root=$('#messages');root.replaceChildren();$('#empty-state').hidden=S.chat.messages.length>0;root.hidden=S.chat.messages.length===0;
  let assistantNumber=0;
  S.chat.messages.forEach((message,index)=>{
    const el=document.createElement('article');el.className='message '+(message.role==='You'?'user':message.role==='Lambda'?'assistant':'system');
    if(message.role==='You'||message.role==='System'){el.textContent=message.text;}
    else{
      assistantNumber++;
      el.innerHTML=`<div class="assistant-header"><span class="assistant-symbol">λ</span><span>${esc(modelLabel(message.model))}</span></div><div class="message-content"></div><div class="message-footer"><button class="copy-response" title="Copy response">${icon('copy')}Copy</button>${index===S.chat.messages.length-1?`<button class="regenerate-response" title="Regenerate in a new saved branch">${icon('refresh')}Try again</button>`:''}<span>${message.tokens==null?'':`${number(message.tokens)} tokens · ${Number(message.seconds||0).toFixed(1)}s`}</span></div>`;
      richText(el.querySelector('.message-content'),message.text);el.querySelector('.copy-response').onclick=e=>copy(message.text,e.currentTarget);
      const retry=el.querySelector('.regenerate-response');if(retry){retry.disabled=S.generating;retry.onclick=()=>startGeneration(true);}
    }
    root.append(el);
  });
  scrollLatest();
}
function streamNode(){
  let node=$('#streaming-message');
  if(!node){
    $('#empty-state').hidden=true;$('#messages').hidden=false;
    node=document.createElement('article');node.id='streaming-message';node.className='message assistant streaming';
    node.innerHTML=`<div class="assistant-header"><span class="assistant-symbol">λ</span><span>${esc(pretty(S.chat.modelName))}</span></div><div class="message-content"><div class="thinking"><span class="thinking-dot"></span>Thinking…</div></div>`;$('#messages').append(node);
  }
  return node;
}
function scrollLatest(){const el=$('#conversation-scroll');el.scrollTop=el.scrollHeight;$('#scroll-bottom').hidden=true;}
function updateComposer(){
  const busy=S?.generating;const updating=applicationUpdate&&applicationUpdate.phase!=='error';const input=$('#message-input');
  $('#send-button').innerHTML=icon(busy?'stop':'up');$('#send-button').type=busy?'button':'submit';
  $('#send-button').setAttribute('aria-label',busy?'Stop response':'Send message');$('#send-button').title=busy?'Stop response':'Send message';
  $('#send-button').disabled=!!updating||!S||(!busy&&(!input.value.trim()||S.quota.remaining<=0));
  $('#new-chat').disabled=!!busy||!!updating;$('#model-button').disabled=!!busy||!!updating;
}
function resizeInput(){const input=$('#message-input');input.style.height='auto';input.style.height=Math.min(170,input.scrollHeight)+'px';updateComposer();}
async function startGeneration(retry=false){
  if(!S||S.generating||(applicationUpdate&&applicationUpdate.phase!=='error'))return;
  const text=$('#message-input').value.trim();if(!retry&&!text)return;
  closePopover();if(!retry){$('#message-input').value='';resizeInput();}
  // The backend reserves usage and persists the user's real message before emitting start.
  const result=await act(retry?'regenerate':'send',retry?{}:{text});
  if(!result){const state=await act('state');if(state)applyState(state);}
  $('#message-input').focus();
}
function closePopover(){const node=$('#popover');node.hidden=true;node.replaceChildren();node.classList.remove('model-picker');node.removeAttribute('role');node.removeAttribute('aria-label');node.onkeydown=null;$('#model-button').setAttribute('aria-expanded','false');popoverAnchor=null;}
function positionPopover(anchor,up=false){
  const node=$('#popover');
  const r=anchor.getBoundingClientRect();const h=Math.min(node.scrollHeight,420),w=Math.min(340,Math.max(240,node.offsetWidth));
  node.style.width=w+'px';node.style.left=Math.min(innerWidth-w-12,Math.max(12,r.left))+'px';
  node.style.top=Math.min(innerHeight-h-12,Math.max(12,up?r.top-h-9:r.bottom+7))+'px';
}
function popover(anchor,content,up=false){
  const node=$('#popover');node.classList.remove('model-picker');node.removeAttribute('role');node.removeAttribute('aria-label');node.onkeydown=null;node.style.width='';
  node.innerHTML=content;node.hidden=false;popoverAnchor=anchor;positionPopover(anchor,up);
  return node;
}
function chatMenu(anchor,row){
  if(popoverAnchor===anchor){closePopover();return;}
  const root=popover(anchor,`<div class="popover-title">CONVERSATION</div><button data-chat-action="rename">${icon('edit')}Rename</button><button data-chat-action="pin">${icon('pin')}${row.pinned?'Unpin':'Pin'} conversation</button><div class="separator"></div><button data-chat-action="archive">${icon('archive')}${archived?'Restore':'Archive'} conversation</button>`);
  root.querySelector('[data-chat-action=rename]').onclick=()=>{closePopover();renameId=row.id;$('#rename-input').value=row.title;$('#rename-dialog').showModal();$('#rename-input').select();};
  root.querySelector('[data-chat-action=pin]').onclick=async()=>{closePopover();await act('pin_chat',{id:row.id});};
  root.querySelector('[data-chat-action=archive]').onclick=async()=>{closePopover();const restore=archived;await act(restore?'restore_chat':'archive_chat',{id:row.id});toast(restore?'Conversation restored.':'Conversation archived.',restore?null:()=>act('restore_chat',{id:row.id}));};
}
function modelMenu(){
  if(popoverAnchor===$('#model-button')){closePopover();return;}
  if(!S||S.generating)return;
  let content='<div class="model-picker-heading">Choose a model<span>On this device</span></div>';
  for(const family of ['mercury','venus','code','terra','other']){
    const rows=S.models.filter(m=>m.installed_revision!=null&&m.family===family);if(!rows.length)continue;
    const current=rows.find(m=>m.id===S.chat.modelId),label=familyNames[family],panel='model-family-'+family;
    content+=`<section class="model-family-section" data-model-family-section="${family}"><button id="${panel}-toggle" class="model-family-row ${current?'current-family':''}" data-model-family="${family}" aria-expanded="false" aria-controls="${panel}"><span class="model-family-emblem" aria-hidden="true">${label.charAt(0)}</span><span class="model-family-label"><strong>${esc(label)}</strong><small>${rows.length} ${rows.length===1?'model':'models'}${current?' · selected':''}</small></span><span class="family-chevron">${icon('chevron')}</span></button><div id="${panel}" class="model-family-versions" role="group" aria-labelledby="${panel}-toggle" hidden>`;
    for(const m of rows){
      const name=pretty(m.name),version=name.startsWith(label+' ')?name.slice(label.length+1):name,selected=S.chat.modelId===m.id;
      content+=`<button class="model-version-option" data-select-model="${esc(m.id)}" aria-label="Use ${esc(name)}" aria-pressed="${selected}" title="${esc(name)}"><span class="model-entry-label"><strong>${esc(version)}</strong><small>${size(m.bytes)}</small></span>${selected?'<span class="tick">'+icon('check')+'</span>':''}</button>`;
    }
    content+='</div></section>';
  }
  content+=`<div class="separator"></div><button id="browse-more-models">${icon('download')}Manage models in Settings</button>`;
  const trigger=$('#model-button'),root=popover(trigger,content,true);root.classList.add('model-picker');root.style.width='310px';root.setAttribute('role','dialog');root.setAttribute('aria-label','Choose a model');trigger.setAttribute('aria-expanded','true');
  const expand=(button,open)=>{
    root.querySelectorAll('[data-model-family]').forEach(b=>{const expanded=b===button&&open;b.setAttribute('aria-expanded',String(expanded));$('#'+b.getAttribute('aria-controls')).hidden=!expanded;});
    positionPopover(trigger,true);button.scrollIntoView({block:'nearest'});
  };
  root.querySelectorAll('[data-model-family]').forEach(button=>button.onclick=()=>expand(button,button.getAttribute('aria-expanded')!=='true'));
  root.querySelectorAll('[data-select-model]').forEach(b=>{b.onclick=async()=>{closePopover();const state=await act('select_model',{id:b.dataset.selectModel});if(state){toast(`Using ${pretty(state.chat.modelName)}.`);$('#message-input').focus();}};});
  root.onkeydown=e=>{
    const button=e.target.closest('button');if(!button)return;
    if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){
      e.preventDefault();const buttons=Array.from(root.querySelectorAll('button')).filter(b=>!b.disabled&&b.getClientRects().length);
      const index=buttons.indexOf(button),next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;buttons[next]?.focus();
    }else if(e.key==='ArrowRight'&&button.dataset.modelFamily){e.preventDefault();if(button.getAttribute('aria-expanded')==='true')$('#'+button.getAttribute('aria-controls')).querySelector('button')?.focus();else expand(button,true);}
    else if(e.key==='ArrowLeft'){const family=button.closest('[data-model-family-section]')?.querySelector('[data-model-family]');if(family){e.preventDefault();expand(family,false);family.focus();}}
    else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closePopover();trigger.focus();}
  };
  $('#browse-more-models').onclick=()=>openSettings('models');
  positionPopover(trigger,true);root.querySelector('[data-model-family]')?.focus();
}
function profileMenu(){
  if(popoverAnchor===$('#profile-button')){closePopover();return;}
  const root=popover($('#profile-button'),`<div class="profile-summary"><strong>${esc(S.preferences.displayName)}</strong><p>${number(S.quota.remaining)} of ${number(S.quota.allowance)} tokens left</p><div class="usage-track"><div class="usage-fill" data-usage-fill style="width:${usagePercent()}%"></div></div><small>Reset: <span data-reset-in>${esc(resetText())}</span></small></div><div class="separator"></div><button id="profile-details">${icon('user')}Profile & usage</button><button id="profile-settings">${icon('settings')}Settings</button>`,true);
  root.querySelector('#profile-details').onclick=()=>openSettings('profile');root.querySelector('#profile-settings').onclick=()=>openSettings('appearance');
}
function openSettings(view='appearance'){
  closePopover();tab=view;renderSettings();if(!$('#settings-dialog').open)$('#settings-dialog').showModal();
}
async function preference(values){const result=await act('preferences',{values});if(!result)return;if(tab!=='profile')renderSettings();else{const name=$('.profile-heading strong');if(name)name.textContent=S.preferences.displayName;}}
function renderSettings(){
  if(!S)return;
  document.querySelectorAll('.settings-nav [data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  const root=$('#settings-content');const p=S.preferences;
  if(tab==='appearance'){
    root.innerHTML=`<h2>Make yourself at home.</h2><p class="section-copy">A space that feels right, day or night.</p><section class="settings-section"><span class="setting-label">Theme</span><div class="theme-options">${['light','dark','system'].map(theme=>`<button class="theme-option ${p.theme===theme?'selected':''}" data-theme-choice="${theme}" aria-pressed="${p.theme===theme}"><span class="theme-preview ${theme}"><i></i></span>${p.theme===theme?'<span class="theme-tick">✓</span>':''}<strong>${theme[0].toUpperCase()+theme.slice(1)}</strong></button>`).join('')}</div></section><section class="settings-section"><span class="setting-label">Accent color</span><div class="accent-options">${['orange','graphite','blue','sage','clay'].map(c=>`<button class="accent-choice ${p.accent===c?'selected':''}" data-color="${c}" aria-label="Use ${c} accent" aria-pressed="${p.accent===c}" title="${c}"></button>`).join('')}</div></section><section class="settings-section"><div class="setting-row"><label for="font-size">Conversation text size<small>A little more room for your words.</small></label><input id="font-size" type="range" min="13" max="20" step="1" value="${p.fontSize}" aria-label="Conversation text size"></div><div class="setting-row"><label for="density">Spacing<small>Choose how much breathing room you prefer.</small></label><select id="density"><option value="comfortable" ${p.density==='comfortable'?'selected':''}>Comfortable</option><option value="compact" ${p.density==='compact'?'selected':''}>Compact</option></select></div></section>`;
    root.querySelectorAll('[data-theme-choice]').forEach(b=>b.onclick=()=>preference({theme:b.dataset.themeChoice}));
    root.querySelectorAll('[data-color]').forEach(b=>b.onclick=()=>preference({accent:b.dataset.color}));
    $('#font-size').oninput=e=>{document.documentElement.style.setProperty('--body-size',e.target.value+'px');};$('#font-size').onchange=e=>preference({fontSize:Number(e.target.value)});$('#density').onchange=e=>preference({density:e.target.value});
  }else if(tab==='models')renderModels(root);
  else if(tab==='chat'){
    root.innerHTML=`<h2>Conversations</h2><p class="section-copy">Pick up where you left off. Chats save automatically on this device.</p><section class="settings-section"><div class="setting-row"><label for="response-tokens">Reply length<small>Maximum tokens in a reply. Also used for new chats.</small></label><select id="response-tokens">${[64,120,192,384,768,1024,2048].map(n=>`<option value="${n}" ${S.chat.settings.max_tokens===n?'selected':''}>${number(n)} tokens</option>`).join('')}</select></div></section><section class="settings-section"><span class="setting-label">Keyboard shortcuts</span><table class="shortcut-table"><tr><td>New conversation</td><td>${command} N</td></tr><tr><td>Search your chats</td><td>${command} K</td></tr><tr><td>Open settings</td><td>${command} ,</td></tr><tr><td>Send a message</td><td>Enter</td></tr><tr><td>New line</td><td>Shift + Enter</td></tr></table></section><p class="subtle-note">Archived conversations stay on your device. Find them with the archive button above your chat list. “Try again” creates a saved branch, so the original reply is kept.</p>`;
    $('#response-tokens').onchange=e=>preference({responseTokens:Number(e.target.value)});
  }else if(tab==='updates'){renderUpdates(root);
  }else{
    root.innerHTML=`<h2>Profile & usage</h2><p class="section-copy">One local profile. The same allowance across your chats and the terminal app.</p><div class="profile-heading"><span class="avatar">${esc(p.displayName.charAt(0).toUpperCase())}</span><div><strong>${esc(p.displayName)}</strong><small>On this device · no account required</small></div></div><div class="setting-row"><label for="display-name">Your name</label><input id="display-name" type="text" maxlength="40" value="${esc(p.displayName)}"></div><section class="settings-section"><label class="profile-share"><input id="share-profile" type="checkbox" ${p.shareProfile?'checked':''}>Use my profile as chat context</label><div class="profile-fields"><label>Age <input id="profile-age" type="number" min="1" max="120" value="${esc(p.age)}" placeholder="Optional"></label><label>Location <input id="profile-location" maxlength="80" value="${esc(p.location)}" placeholder="City or country (optional)"></label><label>Interests <input id="profile-interests" maxlength="160" value="${esc(p.interests)}" placeholder="What do you enjoy? (optional)"></label></div><p class="subtle-note">When enabled, these details are added to each message as local model context. They use input tokens and are not sent to the update server. Memory-capable models can use this information; accuracy depends on the model. Later messages can correct your saved details.</p></section><div class="usage-card"><div class="usage-head"><span>YOUR TOKEN ALLOWANCE</span><span>10-hour window</span></div><div class="usage-number"><span data-remaining>${number(S.quota.remaining)}</span><small> tokens left</small></div><div class="usage-track"><div class="usage-fill" data-usage-fill style="width:${usagePercent()}%"></div></div><div class="usage-caption"><span data-percent>${usagePercent().toFixed(1)}% remaining</span><span>of ${number(S.quota.allowance)}</span></div><div class="usage-stats"><div class="usage-stat"><span>Tokens used</span><strong>${number(S.quota.used)}</strong></div><div class="usage-stat"><span>Resets in</span><strong data-reset-in>${esc(resetText())}</strong></div></div></div><p class="subtle-note">${S.quota.resets_at?'Next reset: '+esc(new Date(S.quota.resets_at).toLocaleString('en-US',{dateStyle:'medium',timeStyle:'short'}))+'.':'Your 10-hour window starts when you send your first message.'}<br>Your remaining allowance is shared with the Lambda terminal app and is not reset when you switch models.</p>`;
    $('#display-name').onchange=e=>preference({displayName:e.target.value.trim()});
    $('#share-profile').onchange=e=>preference({shareProfile:e.target.checked});
    for(const [id,key] of [['profile-age','age'],['profile-location','location'],['profile-interests','interests']])$('#'+id).onchange=e=>preference({[key]:e.target.value.trim()});
  }
}
function renderModels(root){
  root.innerHTML=`<h2>Your models, your choice.</h2><p class="section-copy">Download only what you want to use. Installed models appear in the conversation picker.</p><div class="settings-tools"><div class="segmented"><button data-model-filter="all" class="${modelFilter==='all'?'active':''}">All models</button><button data-model-filter="installed" class="${modelFilter==='installed'?'active':''}">On this device</button></div><button class="secondary-button" id="refresh-models">${icon('refresh')}Refresh list</button></div><div id="model-cards"></div><p class="subtle-note">The small Mercury 1.0 model is included. Other models are downloaded only when you choose them. Refreshing this list does not download model weights.</p>`;
  const list=$('#model-cards');
  for(const family of ['mercury','venus','code','terra','other']){
    const models=S.models.filter(m=>m.family===family&&(modelFilter==='all'||m.installed_revision!=null));if(!models.length)continue;
    const h=document.createElement('h3');h.className='model-family-title';h.textContent=familyNames[family];list.append(h);
    for(const m of models){
      const installed=m.installed_revision!=null;const card=document.createElement('article');card.className='model-card';card.dataset.model=m.id;
      card.innerHTML=`<div class="model-emblem">λ</div><div class="model-description"><h3>${esc(pretty(m.name))}${installed?'<span class="installed-tag">On device</span>':''}</h3><div class="model-details">${esc(familyCopy[family])}<br><span>${size(m.bytes)}</span><span>English</span>${m.local_only?'<span>Local build</span>':''}${m.update_available?'<span>Update available</span>':''}</div><div class="download-state" data-download-id="${esc(m.id)}" hidden><span class="download-label"></span><div class="usage-track"><div class="usage-fill"></div></div></div></div><button class="${installed?'secondary-button':'primary-button'}" data-model-action="${esc(m.id)}" ${S.generating?'disabled':''}>${S.chat.modelId===m.id?'Selected':installed?(m.update_available?'Update':'Use'):'Download'}</button>`;
      const b=card.querySelector('[data-model-action]');if(S.chat.modelId===m.id&&!m.update_available)b.disabled=true;
      b.onclick=async()=>{
        if(S.downloading?.id===m.id){await act('cancel_download');return;}
        if(!installed||m.update_available){
          if(S.downloading){toast('Finish or cancel the current download first.');return;}
          const state=await act('download',{id:m.id});if(state){toast(`${pretty(m.name)} is ready to use.`);renderSettings();}
        }else{const state=await act('select_model',{id:m.id});if(state){renderSettings();toast(`Using ${pretty(m.name)}.`);}}
      };list.append(card);
    }
  }
  root.querySelectorAll('[data-model-filter]').forEach(b=>b.onclick=()=>{modelFilter=b.dataset.modelFilter;renderSettings();});
  $('#refresh-models').onclick=async e=>{const b=e.currentTarget;b.disabled=true;b.textContent='Refreshing…';const state=await act('refresh_catalog');if(state)toast('Model list refreshed. No models were downloaded.');renderSettings();};
  updateDownload();
}
function updateDownload(){
  if(!S)return;
  document.querySelectorAll('[data-model-action]').forEach(button=>{
    const downloading=S.downloading?.id===button.dataset.modelAction;
    if(downloading){button.textContent='Cancel';button.disabled=false;}
    else if(S.downloading){button.disabled=true;}
  });
  if(S.downloading){
    const region=document.querySelector(`[data-download-id="${CSS.escape(S.downloading.id)}"]`);
    if(region){region.hidden=false;region.querySelector('.download-label').textContent=`Downloading · ${S.downloading.percent}%`;region.querySelector('.usage-fill').style.width=S.downloading.percent+'%';}
  }
}

decorate();$('.shortcut').textContent=`${command} N`;$('.search-box kbd').textContent=`${command} K`;
$('#composer').onsubmit=e=>{e.preventDefault();startGeneration();};
$('#send-button').onclick=e=>{if(S?.generating){e.preventDefault();act('stop');$('#generation-status').textContent='Stopping…';}};
$('#message-input').oninput=resizeInput;
$('#message-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!S?.generating)startGeneration();}};
$('#new-chat').onclick=$('#brand-new').onclick=async()=>{closePopover();await act('new_chat');$('#message-input').focus();};
$('#chat-search').oninput=e=>{query=e.target.value;clearTimeout(searchTimer);searchTimer=setTimeout(searchChats,180);};
$('#archive-view').onclick=()=>{archived=!archived;searchChats();};
$('#sidebar-toggle').onclick=()=>document.body.classList.toggle('sidebar-hidden');
$('#model-button').onclick=modelMenu;$('#profile-button').onclick=profileMenu;
$('#settings-button').onclick=()=>openSettings();
$('#chat-actions').onclick=e=>{const row=S?.chats.find(c=>c.id===S.chat.id);if(row)chatMenu(e.currentTarget,row);else toast('Send a message to start this conversation.');};
$('#chat-title').onclick=()=>{if(!S?.chat.id)return;renameId=S.chat.id;$('#rename-input').value=S.chat.title;$('#rename-dialog').showModal();$('#rename-input').select();};
$('#close-settings').onclick=()=>$('#settings-dialog').close();
$('.settings-nav').onclick=e=>{const b=e.target.closest('[data-tab]');if(b){tab=b.dataset.tab;renderSettings();}};
$('#delete-cancel').onclick=()=>$('#delete-dialog').close();
$('#delete-form').onsubmit=async e=>{e.preventDefault();const state=await act('delete_chat',{id:deleteId});if(state){$('#delete-dialog').close();toast('Conversation deleted.');}};
$('#rename-cancel').onclick=()=>$('#rename-dialog').close();
$('#rename-form').onsubmit=async e=>{e.preventDefault();const state=await act('rename_chat',{id:renameId,title:$('#rename-input').value});if(state)$('#rename-dialog').close();};
document.querySelectorAll('.starter').forEach(b=>b.onclick=()=>{$('#message-input').value=b.dataset.prompt;resizeInput();$('#message-input').focus();});
document.addEventListener('pointerdown',e=>{if(!$('#popover').contains(e.target)&&!popoverAnchor?.contains(e.target))closePopover();});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')closePopover();
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();document.body.classList.remove('sidebar-hidden');$('#chat-search').focus();}
});
$('#conversation-scroll').onscroll=()=>{const e=$('#conversation-scroll');$('#scroll-bottom').hidden=e.scrollHeight-e.scrollTop-e.clientHeight<200;};$('#scroll-bottom').onclick=scrollLatest;
window.lambda.onEvent(({event,data})=>{
  if(event==='generation-start'){applyState(data);stream={text:'',tokens:0};streamNode();$('#generation-status').textContent='Thinking…';scrollLatest();}
  else if(event==='generation-text'){
    if(!S||data.chatId!==S.chat.id)return;
    const scroll=$('#conversation-scroll');const follow=scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<180;
    stream=data;richText(streamNode().querySelector('.message-content'),data.text);$('#generation-status').textContent=`${data.tokens} tokens`;
    if(follow)scrollLatest();
  }else if(event==='generation-phase')$('#generation-status').textContent=data.text;
  else if(event==='generation-end'){applyState(data);$('#streaming-message')?.remove();stream=null;}
  else if(event==='download-progress'){if(S){S.downloading=data;updateDownload();}}
  else if(event==='download-end'){applyState(data);if($('#settings-dialog').open&&tab==='models')renderSettings();}
  else if(event==='navigate'){if(data.view==='new')$('#new-chat').click();else openSettings();}
  else if(event==='engine-error'){toast(data.message);$('#generation-status').textContent='Engine disconnected';$('#send-button').disabled=true;}
  else if(event==='application-update'){applicationUpdate=data;updateComposer();if($('#settings-dialog').open&&tab==='updates')renderSettings();}
});
setInterval(liveUsage,1000);
setInterval(()=>{if(S&&!S.generating)act('state');},30000);
updateComposer();act('state').then(value=>{if(value)$('#message-input').focus();else{$('#chat-notice').hidden=false;$('#chat-notice').textContent='The local engine could not start. Close Lambda and open it again.';}});

function confirmDelete(row){
  closePopover();deleteId=row.id;$('#delete-description').textContent=`Delete “${row.title}” from this device? This cannot be undone. Your models and token allowance stay the same.`;$('#delete-dialog').showModal();$('#delete-cancel').focus();
}
function renderUpdates(root){
  let message='Check for a new desktop release for this device. Models are managed separately in Settings → Models.';
  const updating=applicationUpdate&&applicationUpdate.phase!=='error';
  if(checkingUpdates)message='Checking GitHub for desktop updates…';
  else if(applicationUpdate?.phase==='error')message=applicationUpdate.message;
  else if(applicationUpdate?.phase==='downloading')message=`Downloading Desktop ${applicationUpdate.version} · ${applicationUpdate.percent}%`;
  else if(applicationUpdate?.phase==='preparing')message='Download verified. Preparing the application update…';
  else if(applicationUpdate?.phase==='restarting')message='Updating and restarting Lambda…';
  else if(updateResult?.error)message=updateResult.error;
  else if(updateResult?.status==='available')message=`Desktop ${updateResult.latest} is available. You are using ${updateResult.current}.`;
  else if(updateResult?.status==='current')message=`You’re up to date. Desktop ${updateResult.current} is the latest available version.`;
  else if(updateResult?.status==='unpublished')message='This preview has no published desktop release yet. You can view all Lambda releases.';
  else if(desktopInfo.lastUpdate?.status==='error')message='The previous update could not finish: '+desktopInfo.lastUpdate.message;
  const canUpdate=updateResult?.status==='available'&&updateResult.direct&&updateResult.installable;
  root.innerHTML=`<h2>Keep Lambda up to date.</h2><p class="section-copy">Download an update, then Lambda closes and opens again automatically.</p><div class="setting-row"><span>Installed desktop version</span><strong>${esc(desktopInfo.version)}</strong></div><div class="update-status" role="status">${esc(message)}${updating?`<progress class="application-update-progress" max="100" value="${Number(applicationUpdate.percent)||0}" aria-label="Application update progress"></progress>`:''}</div><div class="updates-actions"><button id="check-updates" class="${canUpdate?'secondary-button':'primary-button'}" ${checkingUpdates||updating?'disabled':''}>${icon('refresh')}Check for updates</button>${canUpdate?`<button id="install-update" class="primary-button" ${updating||S?.generating||S?.downloading?'disabled':''}>${icon('download')}${updating?'Updating…':'Update & restart'}</button>`:updateResult&&!updateResult.error?'<button id="open-update" class="secondary-button">View desktop release</button>':''}</div><p class="subtle-note">Your chats, downloaded models, profile and token allowance stay on this device. ${updateResult?.installable===false?esc(updateResult.reason):'Finish any active reply or model download before updating.'}</p>`;
  $('#check-updates').onclick=async()=>{checkingUpdates=true;renderSettings();try{updateResult=await window.lambda.request('check_updates');}catch(error){updateResult={error:error.message};}finally{checkingUpdates=false;if(tab==='updates')renderSettings();}};
  if($('#open-update'))$('#open-update').onclick=()=>window.lambda.openExternal(updateResult.url).catch(error=>toast(error.message));
  if($('#install-update'))$('#install-update').onclick=async()=>{applicationUpdate={phase:'downloading',percent:0,version:updateResult.latest};updateComposer();renderSettings();try{await window.lambda.request('install_update');}catch(error){applicationUpdate={phase:'error',message:error.message};updateComposer();if(tab==='updates')renderSettings();}};
}
window.lambda.request('desktop_info').then(info=>{desktopInfo=info;$('.settings-nav-footer span').textContent='Version '+info.version;}).catch(()=>{});
