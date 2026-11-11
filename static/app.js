const $ = id => document.getElementById(id);
let user = null, page = 1;
async function api(path, opts={}) {
  const response = await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...opts});
  const data = await response.json();
  if(!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function say(message, good=false) { $('status').textContent=message; $('status').style.color=good?'#14663f':'#8a2f18'; }
function item(post, isAdmin=false) {
  const el=document.createElement('article'); el.className='item'+(!post.is_visible?' hidden-item':'');
  const heading=document.createElement('strong'); heading.textContent=post.sender+' → '+post.recipient; el.append(heading);
  const para=document.createElement('p');para.textContent=post.message;el.append(para);
  const date=document.createElement('small'); date.textContent=new Date(post.created_at).toLocaleString()+(post.is_visible?'':' • Hidden');el.append(date);
  if(isAdmin){
    const actions=document.createElement('div');actions.className='actions';
    const toggle=document.createElement('button');toggle.textContent=post.is_visible?'Hide':'Restore';
    toggle.onclick=async()=>{const reason=prompt('Reason for moderation (optional):','');if(reason===null)return;await execute(async()=>{await api('/api/admin/kudos/'+post.id,{method:'PATCH',body:JSON.stringify({is_visible:!post.is_visible,reason})});await refresh();say('Moderation saved',true);});};
    const del=document.createElement('button');del.className='secondary';del.textContent='Delete';
    del.onclick=async()=>{if(!confirm('Permanently delete this kudos?'))return;await execute(async()=>{await api('/api/admin/kudos/'+post.id,{method:'DELETE'});await refresh();say('Kudos deleted',true);});};
    actions.append(toggle,del);el.append(actions);
  }
  return el;
}
async function execute(fn){try{await fn();}catch(e){say(e.message);}}
async function refresh(){
  const feed=await api('/api/kudos?page='+page);
  $('feed').replaceChildren(...(feed.kudos.length?feed.kudos.map(x=>item(x)):[Object.assign(document.createElement('p'),{textContent:'No kudos to show yet.',className:'empty'})]));
  $('pageLabel').textContent='Page '+page;$('prev').disabled=page<=1;$('next').disabled=feed.kudos.length<20;
  if(user.role==='admin'){
    const admin=await api('/api/admin/kudos');
    $('adminFeed').replaceChildren(...(admin.kudos.length?admin.kudos.map(x=>item(x,true)):[Object.assign(document.createElement('p'),{textContent:'No kudos yet.',className:'empty'})]));
  }
}
async function setUser(next){user=next;$('login').hidden=!!user;$('portal').hidden=!user;if(!user)return;
  $('identity').textContent=user.name+' ('+user.role+')';$('adminPanel').hidden=user.role!=='admin';
  const data=await api('/api/users');$('recipient').replaceChildren();
  for(const person of data.users){const opt=document.createElement('option');opt.value=person.id;opt.textContent=person.name;$('recipient').append(opt);}
  page=1;await refresh();
}
$('loginForm').onsubmit=e=>{e.preventDefault();execute(async()=>{const form=new FormData(e.target);const result=await api('/api/login',{method:'POST',body:JSON.stringify(Object.fromEntries(form))});await setUser(result.user);say('Welcome!',true);});};
$('logout').onclick=()=>execute(async()=>{await api('/api/logout',{method:'POST',body:'{}'});await setUser(null);say('Signed out',true);});
$('kudosForm').onsubmit=e=>{e.preventDefault();execute(async()=>{await api('/api/kudos',{method:'POST',body:JSON.stringify({recipient_id:Number($('recipient').value),message:$('message').value})});$('message').value='';$('length').textContent='0 / 500';page=1;await refresh();say('Kudos sent!',true);});};
$('message').oninput=()=>{$('length').textContent=$('message').value.length+' / 500';};
$('prev').onclick=()=>execute(async()=>{if(page>1)page--;await refresh();});
$('next').onclick=()=>execute(async()=>{page++;await refresh();});
execute(async()=>{try{const data=await api('/api/me');await setUser(data.user);}catch{await setUser(null);}});
