const $=id=>document.getElementById(id);let tournaments=[];
async function api(url,opts={}){const r=await fetch(url,{...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||'Request failed');return d}
function msg(s){$('adminMessage').textContent=s}
async function start(){const s=await api('/api/session');if(s.admin){$('loginPanel').hidden=true;$('workspace').hidden=false;await refresh()}else{$('loginPanel').hidden=false;$('workspace').hidden=true}}
async function refresh(){tournaments=await api('/api/tournaments');['teamTournament','bulkTournament','scoreTournament','bulkScoreTournament'].forEach(id=>{const el=$(id);el.innerHTML=tournaments.map(t=>'<option value="'+t.id+'">'+esc(t.name)+'</option>').join('')});if(tournaments.length){await Promise.all([loadTeams(),loadResults()])}}
async function loadTeams(){const tid=$('teamTournament').value;if(!tid)return;const teams=await api('/api/teams?tournament_id='+tid);$('teamList').innerHTML=teams.map(t=>'<div class="compact-row"><span><b>'+esc(t.name)+'</b><br><span class="muted">'+esc(t.players||'Players not set')+'</span></span><button data-highlight="'+t.id+'" data-value="'+(t.highlighted?0:1)+'">'+(t.highlighted?'UNHIGHLIGHT':'HIGHLIGHT')+'</button></div>').join('')||'<p class="muted">No teams registered yet.</p>';$('highlightList').innerHTML=teams.map(t=>'<div class="compact-row"><span>'+esc(t.name)+'</span><button data-highlight="'+t.id+'" data-value="'+(t.highlighted?0:1)+'">'+(t.highlighted?'★ ON':'☆ OFF')+'</button></div>').join('')||'<p class="muted">Add teams to manage highlights.</p>'}
async function loadResults(){const tid=$('scoreTournament').value;if(!tid)return;const rows=await api('/api/results?tournament_id='+tid);$('adminResults').innerHTML=rows.map(r=>'<div class="compact-row"><span><b>M'+r.match_number+' · '+esc(r.team_name)+'</b><br><span class="muted">'+esc(r.map_name)+' · #'+r.placement+' · '+r.kills+' kills · '+(r.kills+r.placement_points)+' pts</span></span><span><button data-edit="'+r.id+'">EDIT</button> <button class="danger" data-delete="'+r.id+'">DELETE</button></span></div>').join('')||'<p class="muted">No results recorded yet.</p>'}
$('loginForm').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/login',{method:'POST',body:JSON.stringify({password:$('password').value})});$('loginMessage').textContent='Signed in.';await start()}catch(err){$('loginMessage').textContent=err.message}});
$('logout').addEventListener('click',async()=>{await api('/api/logout',{method:'POST'});await start()});
$('tournamentForm').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/tournaments',{method:'POST',body:JSON.stringify({name:$('tName').value,status:$('tStatus').value,game:'BGMI'})});$('tName').value='';msg('Tournament created.');await refresh()}catch(err){msg(err.message)}});
$('teamForm').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/teams',{method:'POST',body:JSON.stringify({tournament_id:$('teamTournament').value,name:$('teamName').value,players:$('players').value})});$('teamName').value='';$('players').value='';msg('Team added.');await loadTeams()}catch(err){msg(err.message)}});
$('bulkTeamForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const names=$('bulkTeamNames').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
 if(!names.length){$('bulkMessage').textContent='Paste at least one team name.';return}
 try{
  const d=await api('/api/teams/bulk',{method:'POST',body:JSON.stringify({tournament_id:$('bulkTournament').value,teams:names})});
  $('bulkMessage').textContent='Added '+d.added_count+' team(s); skipped '+d.skipped_count+' duplicate(s).';
  $('bulkTeamNames').value='';
  await loadTeams();
 }catch(err){$('bulkMessage').textContent=err.message}
});
$('scoreForm').addEventListener('submit',async e=>{e.preventDefault();try{const d=await api('/api/results',{method:'POST',body:JSON.stringify({tournament_id:$('scoreTournament').value,match_number:$('match').value,map_name:$('map').value,team_name:$('scoreTeam').value,placement:$('placement').value,kills:$('kills').value,placement_points:$('placementPoints').value})});msg('Score saved · '+d.total_points+' points.');await loadResults()}catch(err){msg(err.message)}});
$('placement').addEventListener('input',()=>{const p=Number($('placement').value);$('placementPoints').value=({1:10,2:6,3:5,4:4,5:3,6:2,7:1,8:1})[p]||0});
$('teamTournament').addEventListener('change',loadTeams);$('scoreTournament').addEventListener('change',loadResults);$('refresh').addEventListener('click',refresh);
document.addEventListener('click',async e=>{const h=e.target.closest('[data-highlight]');const del=e.target.closest('[data-delete]');const edit=e.target.closest('[data-edit]');try{if(h){await api('/api/teams/'+h.dataset.highlight,{method:'PATCH',body:JSON.stringify({highlighted:Number(h.dataset.value)})});await loadTeams()}if(del){if(confirm('Delete this result?')){await api('/api/results/'+del.dataset.delete,{method:'DELETE'});await loadResults()}}if(edit){const id=edit.dataset.edit;const match=prompt('New match number?');if(match===null)return;const placement=prompt('New placement?');if(placement===null)return;const kills=prompt('New kills?');if(kills===null)return;const pp=({1:10,2:6,3:5,4:4,5:3,6:2,7:1,8:1})[Number(placement)]||0;await api('/api/results/'+id,{method:'PATCH',body:JSON.stringify({match_number:Number(match),placement:Number(placement),kills:Number(kills),placement_points:pp})});msg('Result updated.');await loadResults()}}catch(err){msg(err.message)}});
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

async function loadBulkSetup(){
 const tid=$('bulkScoreTournament').value;
 $('bulkMatch').innerHTML='<option value="">Loading matches…</option>';
 $('bulkScoreRows').innerHTML='<p class="muted">Loading registered teams…</p>';
 $('saveBulkScores').disabled=true;
 if(!tid)return;
 try{
  const [teams,schedule]=await Promise.all([
   api('/api/teams?tournament_id='+tid),
   api('/api/schedule?tournament_id='+tid)
  ]);
  $('bulkMatch').innerHTML='<option value="">Choose match</option>'+schedule.map(m=>'<option value="'+m.match_number+'" data-map="'+esc(m.map_name)+'">'+('Match '+m.match_number+' · '+esc(m.map_name)+' · '+m.match_date)+'</option>').join('');
  $('bulkScoreRows').innerHTML=teams.length?'<div class="bulk-score-head"><span>TEAM</span><span>PLACE</span><span>KILLS</span><span>PTS</span></div>'+teams.map(t=>'<div class="bulk-score-row" data-team="'+esc(t.name)+'"><b>'+esc(t.name)+'</b><input class="bulk-place" type="number" min="1" max="'+teams.length+'" placeholder="—" aria-label="'+esc(t.name)+' placement"><input class="bulk-kills" type="number" min="0" placeholder="0" value="0" aria-label="'+esc(t.name)+' kills"><strong class="bulk-points">0</strong></div>').join(''):'<p class="muted">Register teams first.</p>';
  $('saveBulkScores').disabled=!teams.length||!schedule.length;
 }catch(err){$('bulkScoreRows').innerHTML='<p class="message">'+esc(err.message)+'</p>'}
}
function updateBulkPreview(){
 document.querySelectorAll('.bulk-score-row').forEach(row=>{
  const p=Number(row.querySelector('.bulk-place').value),k=Number(row.querySelector('.bulk-kills').value);
  const pp=({1:10,2:6,3:5,4:4,5:3,6:2,7:1,8:1})[p]||0;
  row.querySelector('.bulk-points').textContent=pp+k;
 });
}
$('bulkScoreTournament').addEventListener('change',loadBulkSetup);
$('bulkMatch').addEventListener('change',()=>{
 const opt=$('bulkMatch').selectedOptions[0];
 $('bulkMap').value=opt?opt.dataset.map||'':'';
});
$('bulkScoreRows').addEventListener('input',updateBulkPreview);
$('saveBulkScores').addEventListener('click',async()=>{
 const tid=$('bulkScoreTournament').value,match=$('bulkMatch').value,map=$('bulkMap').value;
 const rows=[...document.querySelectorAll('.bulk-score-row')];
 if(!tid||!match||!rows.length){$('bulkScoreMessage').textContent='Choose a tournament and match.';return}
 const entries=rows.map(row=>({team_name:row.dataset.team,placement:row.querySelector('.bulk-place').value,kills:row.querySelector('.bulk-kills').value}));
 if(entries.some(x=>x.placement===''||x.kills==='')){$('bulkScoreMessage').textContent='Enter placement and kills for every team.';return}
 if(!confirm('Save all '+entries.length+' team scores for Match '+match+'? Existing scores for this match will be replaced.'))return;
 $('saveBulkScores').disabled=true;
 try{
  const d=await api('/api/results/bulk',{method:'POST',body:JSON.stringify({tournament_id:tid,match_number:match,map_name:map,entries})});
  $('bulkScoreMessage').textContent='Saved '+d.saved+' team scores for Match '+match+'.';
  await Promise.all([loadResults(),loadBulkSetup()]);
 }catch(err){$('bulkScoreMessage').textContent=err.message}
 finally{$('saveBulkScores').disabled=false}
});

start().catch(e=>msg(e.message));