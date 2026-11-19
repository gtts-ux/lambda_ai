/* Image mode stays separate from the persisted text-chat payload. */
let workspaceMode='chat',selectedImage=null,pendingImageDelete=null,imageFingerprint='',lastCompletedImage=null;
function showWorkspace(mode){
  workspaceMode=mode;const image=mode==='image';
  $('#image-playground').hidden=!image;$('#conversation-scroll').hidden=image;$('.composer-area').hidden=image;
  $('#chat-actions').hidden=image;$('#chat-title').textContent=image?'Image Playground':S?.chat.title||'New chat';
  $('#chat-title').disabled=image;
  $('#image-playground-nav').classList.toggle('active',image);$('#scroll-bottom').hidden=true;
  if(image){renderPlayground();$('#image-prompt').focus();}
}
function showImage(row){
  if(!row)return;selectedImage=row.id;$('#image-result').src=row.dataUrl;$('#image-result').alt=row.prompt;
  $('#image-result').hidden=false;$('#image-placeholder').hidden=true;$('#image-result-actions').hidden=false;
  $('#image-prompt').value=row.prompt;$('#image-seed').value=row.seed;
  const credits=$('#image-reference-list');credits.replaceChildren();
  for(const ref of row.selectedReferences||[]){
    const p=document.createElement('p'),a=document.createElement('a');a.textContent=ref.title||ref.provider;a.href=ref.source_url||'#';
    a.onclick=e=>{e.preventDefault();window.lambda.openExternal(a.href).catch(error=>toast(error.message));};
    p.append(a,document.createTextNode(' · '+(ref.credit||ref.provider||'')));credits.append(p);
  }
  $('#image-reference-details').hidden=!credits.children.length;
}
function renderPlayground(){
  if(!S)return;const job=S.imageJob||{},busy=S.generating,installed=S.imageModels?.some(m=>m.installed_revision!=null);
  $('#image-generate').disabled=!!busy||!installed||!!applicationUpdate&&applicationUpdate.phase!=='error';
  $('#image-generate').textContent=job.state==='running'?'Creating…':'Create image';
  $('#image-stop').hidden=job.state!=='running';
  $('#image-model-settings').hidden=installed;$('#image-progress').hidden=!job.phase;
  $('#image-phase').textContent=job.phase||'';$('#image-percent').value=job.percent||0;
  $('#image-canvas').classList.toggle('creating',job.state==='running');
  $('#image-delete').disabled=!!busy;
  const fingerprint=JSON.stringify((S.images||[]).map(r=>r.id));
  if(fingerprint!==imageFingerprint){
    imageFingerprint=fingerprint;const list=$('#image-history');list.replaceChildren();
    for(const row of S.images||[]){const button=document.createElement('button');button.className='image-history-item';button.title=row.prompt;
      const im=document.createElement('img');im.src=row.dataUrl;im.alt=row.prompt;const label=document.createElement('span');label.textContent=row.prompt;
      button.append(im,label);button.onclick=()=>showImage(row);list.append(button);}
    if(!(S.images||[]).some(row=>row.id===selectedImage)){
      selectedImage=null;$('#image-result').hidden=true;$('#image-result-actions').hidden=true;$('#image-placeholder').hidden=false;$('#image-reference-details').hidden=true;
    }
  }
  if(job.state==='completed'&&job.id!==lastCompletedImage){lastCompletedImage=job.id;showImage(S.images?.find(row=>row.id===job.id));}
  else if(!selectedImage&&S.images?.length)showImage(S.images[0]);
  if(workspaceMode==='image')$('#chat-title').textContent='Image Playground';
}
$('#image-playground-nav').onclick=()=>showWorkspace('image');
$('#image-model-settings').onclick=()=>openSettings('models');
$('#image-stop').onclick=()=>act('stop');
$('#image-form').onsubmit=async e=>{
  e.preventDefault();if(S?.generating)return;const prompt=$('#image-prompt').value.trim();if(!prompt)return;
  try{applyState(await window.lambda.request('generate_image',{prompt,seed:Number($('#image-seed').value)}));}
  catch(error){
    await act('state');
    // Failed generation is already explained inline beside the prompt.
    if(!S?.imageJob?.phase||S.imageJob.state!=='failed')toast(friendlyError(error));
  }
};
$('#image-save').onclick=()=>{if(selectedImage)window.lambda.saveImage(selectedImage).catch(error=>toast(error.message));};
$('#image-delete').onclick=()=>{pendingImageDelete=selectedImage;$('#delete-image-dialog').showModal();};
$('#delete-image-cancel').onclick=()=>$('#delete-image-dialog').close();
$('#delete-image-form').onsubmit=async e=>{e.preventDefault();const result=await act('delete_image',{id:pendingImageDelete});if(result)$('#delete-image-dialog').close();};
window.lambda.onEvent(({event,data})=>{
  if(event==='image-request'){showWorkspace('image');$('#image-prompt').value=data.prompt;if(!S.imageModels?.some(m=>m.installed_revision!=null))toast('Download Orion Image 1 in Settings to create this image.');}
  if(event==='image-start'){applyState(data);showWorkspace('image');}
  if(event==='image-progress'){if(S){S.imageJob=data;renderPlayground();}}
  if(event==='image-end'){applyState(data);renderPlayground();}
});
