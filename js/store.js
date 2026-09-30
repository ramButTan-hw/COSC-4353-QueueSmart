/* Same-browser demo data. This is not a server or authentication boundary. */
(function () {
  'use strict';
  const KEY = 'queuesmart.shared.v1';
  const seed = { services: [
    {id:1,name:'Password Reset',description:'Account access and password recovery.',duration:10,priority:'high',open:true,queue:[]},
    {id:2,name:'Wi-Fi / Network',description:'Campus Wi-Fi and device connectivity.',duration:15,priority:'medium',open:true,queue:[]},
    {id:3,name:'Printing',description:'Printing setup, credits, and troubleshooting.',duration:5,priority:'low',open:false,queue:[]}
  ], history:[] };
  function read() { const raw=localStorage.getItem(KEY); return raw ? JSON.parse(raw) : structuredClone(seed); }
  function save(data) { localStorage.setItem(KEY,JSON.stringify(data)); window.dispatchEvent(new Event('queue-change')); }
  function active(data=read()) { const id=window.currentUser.id; const service=data.services.find(s=>s.queue.some(u=>u.id===id)); if(!service)return null; const index=service.queue.findIndex(u=>u.id===id);return {service,index,user:service.queue[index]}; }
  function send(user,message,type){ notify('student',message,type,{recipientId:user.id}); }
  function positions(service,before){service.queue.forEach((u,i)=>{if(before.some(x=>x.id===u.id)&&before.findIndex(x=>x.id===u.id)!==i)send(u,`You moved to position ${i+1} in ${service.name}`,'info');});if(service.open&&service.queue.length&&service.queue[0].id!==before[0]?.id)send(service.queue[0],`You're next for ${service.name}, please head to the help desk`,'warning');}
  function change(serviceId,action,userId){
    const data=read(),s=data.services.find(s=>s.id===Number(serviceId));if(!s)throw Error('Service no longer exists.');const before=s.queue.slice();
    if(action==='join'){
      if(!s.open)throw Error('This queue is closed.');if(active(data))throw Error('Leave your current queue before joining another.');
      const u={id:window.currentUser.id,name:window.currentUser.name};s.queue.push(u);send(u,`You joined ${s.name} at position ${s.queue.length}`,'success');notify('staff',`New student in ${s.name}`,'info');
    }else if(action==='toggle'){
      s.open=!s.open;s.queue.forEach(u=>send(u,`${s.name} queue is now ${s.open?'open':'closed'}`,s.open?'info':'warning'));if(s.open&&s.queue.length)send(s.queue[0],`You're next for ${s.name}, please head to the help desk`,'warning');
    }else{
      const index=action==='serve'?0:s.queue.findIndex(u=>u.id===userId);
      if(index<0||!s.queue.length)return;if(action==='serve'&&!s.open)throw Error('Open this queue before serving.');
      if(action==='up'||action==='down'){const to=index+(action==='up'?-1:1);if(to<0||to>=s.queue.length)return;[s.queue[index],s.queue[to]]=[s.queue[to],s.queue[index]];}
      else if(['serve','remove','leave'].includes(action)){
        const [u]=s.queue.splice(index,1);data.history.unshift({userId:u.id,date:Date.now(),serviceName:s.name,outcome:action==='serve'?'Served':action==='remove'?'Removed':'Left queue'});
        if(action==='leave')notify('staff',`A student left the ${s.name} queue`,'info');
        else send(u,action==='serve'?`You've been served for ${s.name}`:`You were removed from the ${s.name} queue`,action==='serve'?'success':'error');
      }else return;
    }
    if(action!=='toggle')positions(s,before);save(data);
  }
  function saveService(values,id){const data=read();const s=data.services.find(s=>s.id===id);if(s)Object.assign(s,values);else data.services.push({id:Math.max(0,...data.services.map(s=>s.id))+1,...values,open:false,queue:[]});save(data);}
  window.QueueStore={read,active,change,saveService};
  window.addEventListener('storage',e=>{if(e.key===KEY)window.dispatchEvent(new Event('queue-change'));});
})();
