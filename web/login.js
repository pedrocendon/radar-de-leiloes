'use strict';
const form=document.getElementById('auth-form'),error=document.getElementById('auth-error'),submit=document.getElementById('auth-submit');
const invite=new URLSearchParams(location.hash.slice(1)).get('convite');
if(invite){
 history.replaceState(null,'','/login');
 document.getElementById('auth-title').textContent='Crie sua conta';
 document.getElementById('auth-intro').textContent='Seu convite já identifica o e-mail. Escolha uma senha com pelo menos 12 caracteres.';
 document.getElementById('name-field').hidden=false;form.elements.name.required=true;
 document.getElementById('email-field').hidden=true;form.elements.email.required=false;
 form.elements.password.minLength=12;form.elements.password.autocomplete='new-password';
 submit.textContent='Criar minha conta';
 document.getElementById('login-help').textContent='Convites são pessoais, valem por 24 horas e podem ser usados uma única vez.';
}
document.getElementById('show-password').onchange=e=>form.elements.password.type=e.target.checked?'text':'password';
form.onsubmit=async e=>{
 e.preventDefault();error.hidden=true;submit.disabled=true;submit.textContent='Aguarde…';
 try{
  const response=await fetch('/auth/'+(invite?'register':'login'),{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Web':'1'},body:JSON.stringify({email:form.elements.email.value,name:form.elements.name.value,password:form.elements.password.value,invite})});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Não foi possível entrar. Tente novamente.');
  location.replace('/');
 }catch(exc){error.textContent=exc.message||'Confira sua conexão e tente novamente.';error.hidden=false;}
 finally{submit.disabled=false;submit.textContent=invite?'Criar minha conta':'Entrar';}
};
