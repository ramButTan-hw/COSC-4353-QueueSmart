/* Login is per-tab so student and staff views can be tested side by side. */
(function(){
  let user;try{user=JSON.parse(sessionStorage.getItem('queuesmart.session'));}catch(_){}
  const admin=location.pathname.endsWith('/admin.html');
  if(!user || !sessionStorage.getItem('queuesmart.token') || user.role!==(admin?'staff':'student')){location.replace('front%20page.html');return;}
  window.currentUser=user;
  document.addEventListener('DOMContentLoaded',()=>{
    const link=document.createElement('a');link.href='front%20page.html';link.textContent='Log out';link.style.cssText='font-size:14px;white-space:nowrap';
    link.addEventListener('click',()=>{sessionStorage.removeItem('queuesmart.session');sessionStorage.removeItem('queuesmart.token');});
    (document.querySelector('.header-actions')||document.querySelector('.user-area')).appendChild(link);
  });
})();
