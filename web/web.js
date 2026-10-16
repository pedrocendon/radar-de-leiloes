'use strict';
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
window.addEventListener('radar-state',event=>{
 const data=event.detail;
 document.getElementById('account-name').textContent=data.web.name;
 document.getElementById('account-email').textContent=data.web.email;
 document.getElementById('download-csv').disabled=!data.excel.exists||data.job.busy;
});
async function accountAction(action,data={}){
 const response=await fetch('/auth/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Web':'1','X-Radar-Token':document.querySelector('meta[name="radar-csrf"]').content},body:JSON.stringify(data)});
 if(response.status===401){location.replace('/login');return;}
 const result=await response.json();if(!response.ok)throw Error(result.error||'Não foi possível concluir.');
 location.replace('/login');
}
document.getElementById('close-app').onclick=async()=>{try{await accountAction('logout');}catch(e){toast(e.message);}};
document.getElementById('password-form').onsubmit=async e=>{
 e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;
 try{await accountAction('password',Object.fromEntries(new FormData(e.target)));}
 catch(error){document.getElementById('password-message').textContent=error.message;}
 finally{button.disabled=false;}
};
document.getElementById('download-csv').onclick=async()=>{
 try{
  const response=await fetch('/api/csv');
  if(response.status===401){location.replace('/login');return;}
  if(!response.ok)throw Error((await response.json()).error);
  const href=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=href;link.download='Radar-de-Leiloes.csv';link.click();setTimeout(()=>URL.revokeObjectURL(href),10000);
 }catch(error){toast(error.message);}
};
