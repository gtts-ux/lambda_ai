/* Image mode stays separate from the persisted text-chat payload. */
let workspaceMode='chat',selectedImage=null,pendingImageDelete=null,imageFingerprint='',lastCompletedImage=null,imageModelFingerprint='',imageModelChanging=false;
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
  $('#image-prompt').value=row.prompt;$('#image-size').value=String(row.width||256);renderImagePrice();
  $('#image-result-model').textContent=pretty(row.modelName||row.model||'Orion');
  const credits=$('#image-reference-list');credits.replaceChildren();
  for(const ref of row.selectedReferences||[]){
    const p=document.createElement('p'),a=document.createElement('a');a.textContent=ref.title||ref.provider;a.href=ref.source_url||'#';
    a.onclick=e=>{e.preventDefault();window.lambda.openExternal(a.href).catch(error=>toast(error.message));};
    p.append(a,document.createTextNode(' · '+(ref.credit||ref.provider||'')));credits.append(p);
  }
  $('#image-reference-details').hidden=!credits.children.length;
}
function imageQuote(){
  const words=($('#image-prompt').value.normalize('NFKC').match(/[\p{L}\p{N}_]+(?:['’\-][\p{L}\p{N}_]+)*/gu)||[]).length;
  const size=Number($('#image-size').value),count=Number($('#image-count').value),multiplier=size/256;
  const model=S?.imageModels?.find(m=>m.id===S.selectedImageModel),rate=model?.tokens_per_word||1000;
  if(![256,512,1024].includes(size)||!Number.isInteger(count)||count<1||count>8)return null;
  const perImage=words*rate*multiplier;return {words,size,count,multiplier,rate,perImage,total:perImage*count};
}
function renderImagePrice(){
  const quote=imageQuote(),busy=!!S?.generating;
  $('#image-price-breakdown').textContent=!quote?'Choose 1–8 images.':!quote.words?'Add a description to see the cost.':`${quote.words} word${quote.words===1?'':'s'} × ${number(quote.rate)} × ${quote.multiplier} = ${number(quote.perImage)} tokens per image`;
  const insufficient=quote&&S&&!busy&&quote.total>S.quota.remaining;
  $('#image-price-total').textContent=quote?`${number(quote.total)} tokens${quote.count>1?' · '+quote.count+' images':''}${insufficient?' · not enough remaining':''}`:'—';
  $('#image-native-notice').hidden=!quote||quote.size===256;
  const affordable=quote&&quote.words>0&&!insufficient;
  $('#image-generate').disabled=busy||imageModelChanging||!S?.imageModels?.some(m=>m.installed_revision!=null)||!affordable||!!applicationUpdate&&applicationUpdate.phase!=='error';
  return affordable;
}
function renderPlayground(){
  if(!S)return;const job=S.imageJob||{},busy=S.generating,installed=S.imageModels?.some(m=>m.installed_revision!=null);
  const models=(S.imageModels||[]).filter(m=>m.installed_revision!=null),picker=$('#image-model');
  const modelFingerprint=JSON.stringify(models.map(m=>[m.id,m.name,m.installed_revision]));
  if(modelFingerprint!==imageModelFingerprint||!picker.options.length){
    imageModelFingerprint=modelFingerprint;picker.replaceChildren();
    if(!models.length){const option=document.createElement('option');option.textContent='Download a model in Settings';option.value='';picker.append(option);}
    for(const model of models){const option=document.createElement('option');option.value=model.id;option.textContent=pretty(model.name);picker.append(option);}
  }
  picker.value=S.selectedImageModel||'';picker.disabled=!!busy||imageModelChanging||!models.length;
  const active=models.find(m=>m.id===S.selectedImageModel);
  $('#image-model-description').textContent=active?.description||'Choose and download individual models in Settings.';
  const affordable=renderImagePrice(),count=Number($('#image-count').value);
  $('#image-generate').disabled=!!busy||imageModelChanging||!installed||!affordable||!!applicationUpdate&&applicationUpdate.phase!=='error';
  $('#image-generate').textContent=job.state==='running'?'Creating…':count>1?`Create ${count} images`:'Create image';
  for(const id of ['#image-prompt','#image-count','#image-size'])$(id).disabled=!!busy;
  $('#image-stop').hidden=job.state!=='running';
  $('#image-model-settings').textContent=installed?'Manage image models':'Download model in Settings';
  $('#image-model-settings').disabled=!!busy;$('#image-progress').hidden=!job.phase;
  $('#image-phase').textContent=job.phase||'';$('#image-percent').value=job.percent||0;
  $('#image-canvas').classList.toggle('creating',job.state==='running');
  $('#image-delete').disabled=!!busy;
  const fingerprint=JSON.stringify((S.images||[]).map(r=>r.id));
  if(fingerprint!==imageFingerprint){
    imageFingerprint=fingerprint;const list=$('#image-history');list.replaceChildren();
    for(const row of S.images||[]){const button=document.createElement('button');button.className='image-history-item';button.title=row.prompt;
      const im=document.createElement('img');im.src=row.dataUrl;im.alt=row.prompt;const label=document.createElement('span');label.textContent=row.prompt;
      button.title=`${row.prompt} · ${pretty(row.modelName||row.model||'Orion')}`;
      button.append(im,label);button.onclick=()=>showImage(row);list.append(button);}
    if(!(S.images||[]).some(row=>row.id===selectedImage)){
      selectedImage=null;$('#image-result').hidden=true;$('#image-result-actions').hidden=true;$('#image-placeholder').hidden=false;$('#image-reference-details').hidden=true;
    }
  }
  if(job.id&&job.id!==lastCompletedImage){lastCompletedImage=job.id;showImage(S.images?.find(row=>row.id===job.id));}
  else if(!selectedImage&&S.images?.length)showImage(S.images[0]);
  if(workspaceMode==='image')$('#chat-title').textContent='Image Playground';
}
$('#image-playground-nav').onclick=()=>showWorkspace('image');
$('#image-model-settings').onclick=()=>openSettings('models');
$('#image-model').onchange=async()=>{
  const id=$('#image-model').value;if(!id||S?.generating||imageModelChanging)return;
  imageModelChanging=true;$('#image-model').disabled=true;renderImagePrice();
  try{await act('select_image_model',{id});}
  finally{imageModelChanging=false;renderPlayground();}
};
$('#image-stop').onclick=()=>act('stop');
$('#image-form').onsubmit=async e=>{
  e.preventDefault();if(S?.generating||imageModelChanging)return;const prompt=$('#image-prompt').value.trim();if(!prompt)return;
  try{applyState(await window.lambda.request('generate_image',{prompt,modelId:$('#image-model').value,count:Number($('#image-count').value),size:Number($('#image-size').value)}));}
  catch(error){
    await act('state');
    // Failed generation is already explained inline beside the prompt.
    if(!S?.imageJob?.phase||S.imageJob.state!=='failed')toast(friendlyError(error));
  }
};
for(const id of ['#image-prompt','#image-count','#image-size'])$(id).addEventListener('input',renderPlayground);
$('#image-save').onclick=()=>{if(selectedImage)window.lambda.saveImage(selectedImage).catch(error=>toast(error.message));};
$('#image-delete').onclick=()=>{pendingImageDelete=selectedImage;$('#delete-image-dialog').showModal();};
$('#delete-image-cancel').onclick=()=>$('#delete-image-dialog').close();
$('#delete-image-form').onsubmit=async e=>{e.preventDefault();const result=await act('delete_image',{id:pendingImageDelete});if(result)$('#delete-image-dialog').close();};
window.lambda.onEvent(({event,data})=>{
  if(event==='image-request'){showWorkspace('image');$('#image-prompt').value=data.prompt;if(!S.imageModels?.some(m=>m.installed_revision!=null))toast('Download an image model in Settings to create this image.');}
  if(event==='image-start'){applyState(data);showWorkspace('image');}
  if(event==='image-progress'){if(S){S.imageJob=data;renderPlayground();}}
  if(event==='image-end'){applyState(data);renderPlayground();}
  if(event==='image-result'){applyState(data);renderPlayground();}
});
