const $=id=>document.getElementById(id);let activeTournament=null;
async function api(url,opts={}){const r=await fetch(url,{...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||'Request failed');return d}
async function loadTournaments(){try{const ts=await api('/api/tournaments');const s=$('tournamentSelect');s.innerHTML='';if(!ts.length){s.innerHTML='<option value="">No tournaments yet</option>';$('standings').innerHTML='<tr><td colspan="6" class="empty">Tournament data will appear when an admin creates a tournament.</td></tr>';return}ts.forEach(t=>{const o=document.createElement('option');o.value=t.id;o.textContent=t.name;s.append(o)});const mainBoard=ts.find(t=>t.name==='PMGC 2026');if(mainBoard)s.value=mainBoard.id;activeTournament=s.value;await loadBoard()}catch(e){$('tournamentMeta').textContent=e.message}}
async function loadBoard(){activeTournament=$('tournamentSelect').value;if(!activeTournament)return;const [ts,rows,res]=await Promise.all([api('/api/tournaments'),api('/api/standings?tournament_id='+activeTournament),api('/api/results?tournament_id='+activeTournament)]);const t=ts.find(x=>String(x.id)===String(activeTournament));const isGauntlet=!!t&&t.name==='PMGC 2026 - The Gauntlet';const isLastChance=!!t&&t.name==='PMGC 2026 - Last Chance';$('tournamentMeta').textContent=t?t.game+' · '+t.status:'';$('standings').innerHTML=rows.length?rows.map(r=>'<tr class="'+(r.highlighted?'highlight':'')+'"><td class="rank">'+r.rank+'</td><td>'+(r.highlighted?'★ ':'')+esc(r.team_name)+'</td><td>'+r.matches_played+'</td><td>'+r.total_kills+'</td><td>'+r.placement_points+'</td><td class="points">'+r.total_points+'</td></tr>').join(''):'<tr><td colspan="6" class="empty">No scores entered yet. Check back when the first match is recorded.</td></tr>';$('results').innerHTML=res.length?res.map(r=>'<article class="result-card"><div class="eyebrow">MATCH '+r.match_number+' · '+esc(r.map_name)+'</div><h3>'+esc(r.team_name)+'</h3><div>Placement: <strong>#'+r.placement+'</strong></div><div>Kills: <strong>'+r.kills+'</strong></div><div>Total: <strong>'+(r.kills+r.placement_points)+'</strong> points</div></article>').join(''):'<div class="empty">No match results have been added yet.</div>';await Promise.all([loadSchedule(t),loadQualification(isGauntlet,isLastChance,t),loadSmashRule(t)])}
async function loadSchedule(t){const section=$('schedule');const heading=section.querySelector('h2');const eyebrow=section.querySelector('.eyebrow');const note=section.querySelector('.note');eyebrow.textContent=t?t.name.toUpperCase()+' · SCHEDULE':'TOURNAMENT SCHEDULE';heading.textContent='Match schedule';note.textContent=t&&t.name.includes('Group')?'12 matches · 6 each matchday. Dates confirmed; maps and start times will be added when officially announced.':'Schedule details for the selected tournament.';if(!t){$('scheduleGrid').innerHTML='<div class="empty">Select a tournament to view its schedule.</div>';return}const rows=await api('/api/schedule?tournament_id='+t.id);$('scheduleGrid').innerHTML=rows.map(r=>'<article class="result-card"><div class="eyebrow">'+(r.match_date||'SCHEDULED MATCH')+'</div><h3>Match '+r.match_number+' · '+(r.map_name==='TBA'?'Map TBA':esc(r.map_name))+'</h3>'+(r.start_time_trt!=='TBA'?'<div>Turkey: <strong>'+r.start_time_trt+' TRT</strong></div>':'')+(r.start_time_ist!=='TBA'?'<div>India: <strong>'+r.start_time_ist+' IST</strong></div>':'')+'</article>').join('')||'<div class="empty">No matches scheduled for this tournament yet.</div>'}
async function loadQualification(isGauntlet,isLastChance,t){const section=$('qualification');const isGroup=!!t&&t.name.includes('Group');section.style.display=(isGauntlet||isGroup||isLastChance)?'':'none';if(!isGauntlet&&!isGroup&&!isLastChance){$('qualifiedTeams').innerHTML='';return}if(isLastChance){const q=await api('/api/last-chance-qualification?tournament_id='+t.id);$('qualification').querySelector('h2').textContent='Last Chance qualification';$('qualification').querySelector('.eyebrow').textContent='ROAD TO THE GRAND FINALS';const label=q.locked?'FINAL QUALIFICATION CONFIRMED':'PROVISIONAL QUALIFICATION';$('qualificationStatus').innerHTML='<div class="eyebrow">'+label+'</div><h3>'+q.complete_matches+' / '+q.required_matches+' matches completed</h3><p class="muted">Top 3 → Grand Finals · Remaining 13 eliminated. Rankings update after every recorded match.</p><p class="muted">Tiebreaker: '+esc(q.tiebreaker)+'.</p>';$('qualifiedTeams').innerHTML=q.teams.map(t=>'<article class="result-card"><div class="eyebrow">#'+t.rank+' · '+esc(t.status.toUpperCase())+'</div><h3>'+esc(t.team_name)+'</h3><div>Total points: <strong>'+t.total_points+'</strong></div><div>Kills: '+t.kills+' · Placement: '+t.placement_points+'</div></article>').join('');return}if(isGroup){const q=await api('/api/group-qualification?tournament_id='+t.id);const label=q.locked?'FINAL GROUP PLACEMENTS':'PROVISIONAL GROUP PLACEMENTS';$('qualification').querySelector('h2').textContent='Group Stage qualification';$('qualification').querySelector('.eyebrow').textContent='ROAD TO GRAND FINALS & LAST CHANCE';$('qualificationStatus').innerHTML='<div class="eyebrow">'+label+'</div><h3>'+q.complete_matches+' / '+q.required_matches+' matches completed</h3><p class="muted">Top 3 → Grand Finals · 4th–11th → Last Chance · 12th–16th eliminated. Rankings update after every recorded match.</p><p class="muted">Tiebreaker: '+esc(q.tiebreaker)+'.</p>';$('qualifiedTeams').innerHTML=q.teams.map(t=>'<article class="result-card"><div class="eyebrow">#'+t.rank+' · '+esc(t.status.toUpperCase())+'</div><h3>'+esc(t.team_name)+'</h3><div>Total points: <strong>'+t.total_points+'</strong></div><div>Kills: '+t.kills+' · Placement: '+t.placement_points+'</div></article>').join('');return} $('qualification').querySelector('h2').textContent='Top 6 qualification';$('qualification').querySelector('.eyebrow').textContent='ROAD TO THE GRAND FINALS';const ts=await api('/api/tournaments');const stage=ts.find(x=>x.name==='PMGC 2026 - The Gauntlet');if(!stage){$('qualificationStatus').innerHTML='<p class="muted">Gauntlet qualification tracker will appear here.</p>';$('qualifiedTeams').innerHTML='';return}const q=await api('/api/qualification?tournament_id='+stage.id);$('qualificationStatus').innerHTML=q.locked?'<div class="eyebrow">FINAL QUALIFICATION CONFIRMED</div><h3>Top 6 have secured Grand Finals places 💚💙</h3><p>'+q.complete_matches+' of '+q.required_matches+' matches completed.</p><p class="muted">Tiebreaker: '+esc(q.tiebreaker)+'.</p>':'<div class="eyebrow">LIVE QUALIFICATION RACE</div><h3>'+q.complete_matches+' / '+q.required_matches+' matches completed</h3><p class="muted">Current provisional Top 6 · Rankings update after every recorded match. Tiebreaker: '+esc(q.tiebreaker)+'.</p>';$('qualifiedTeams').innerHTML=q.qualified.map(t=>'<article class="result-card"><div class="eyebrow">'+(q.locked?'QUALIFIED':'PROVISIONAL TOP 6')+' · #'+t.rank+'</div><h3>'+esc(t.team_name)+'</h3><div>Total points: <strong>'+t.total_points+'</strong></div><div>Kills: '+t.kills+' · Placement: '+t.placement_points+'</div></article>').join('')}

async function loadSmashRule(t){
 const section=$('smashRule');
 const isFinals=!!t&&t.name==='PMGC 2026 - Grand Finals';
 section.style.display=isFinals?'':'none';
 if(!isFinals)return;
 const q=await api('/api/smash-rule?tournament_id='+t.id);
 let status='';
 if(q.champion){
  status='<div class="eyebrow">'+(q.fallback?'19-MATCH FALLBACK':'CHAMPION CONFIRMED')+'</div><h3>🏆 '+esc(q.champion)+' are PMGC 2026 champions!</h3><p>'+(q.fallback?'No Match Point-eligible team secured a WWCD. Highest total points after Match 19 decides the champion.':'Won Match '+q.champion_match+' after reaching Match Point eligibility.')+'</p>';
 }else if(q.threshold===null){
  status='<div class="eyebrow">MATCH POINT NOT ACTIVE</div><h3>'+q.complete_matches+' / 19 matches completed</h3><p class="muted">The threshold will be calculated after Match 12 is fully recorded.</p>';
 }else{
  status='<div class="eyebrow">MATCH POINT ACTIVE</div><h3>Threshold: '+q.threshold+' points</h3><p class="muted">'+q.complete_matches+' / 19 matches completed. Teams reaching '+q.threshold+' points become eligible from the following match. The first eligible team to win a WWCD becomes champion.</p>';
 }
 $('smashStatus').innerHTML=status+'<p class="muted">Match Point threshold = leading team’s total after Match 12 + 10. Tiebreaker: '+esc(q.tiebreaker)+'.</p>';
 if(q.champion){$('smashEligible').innerHTML='';}
 else {
 $('smashEligible').innerHTML=q.threshold===null?'<article class="result-card"><h3>Waiting for Match 12</h3><p class="muted">Enter complete results for all 16 teams in Match 12 to calculate the threshold.</p></article>':(q.eligible_teams.length?q.eligible_teams.map(t=>'<article class="result-card"><div class="eyebrow">MATCH POINT ELIGIBLE</div><h3>'+esc(t.team_name)+'</h3><div>Total points: <strong>'+t.total_points+'</strong></div></article>').join(''):'<article class="result-card"><h3>No eligible teams yet</h3><p class="muted">Eligibility will update after each completed match.</p></article>');
 }
 const mapState=await api('/api/grand-finals-map-selection?tournament_id='+t.id);
 if(!mapState.match_18_complete){
  $('smashMapSelection').innerHTML='<h3>Waiting for Match 18</h3><p class="muted">'+mapState.complete_matches+' / 18 matches completed. The Match 19 map selection will appear after all 16 teams’ Match 18 results are recorded.</p>';
 }else if(mapState.selection){
  const s=mapState.selection, leader=mapState.leader_after_match_18;
  $('smashMapSelection').innerHTML='<div class="eyebrow">MATCH 19 MAP CONFIRMED</div><h3>'+esc(s.selected_map)+'</h3><p>Erangel Showmatch winner: <strong>'+esc(s.showmatch_winner)+'</strong></p><p>Map banned: <strong>'+esc(s.banned_map)+'</strong></p><p>Map selected by Match 18 leader: <strong>'+esc(leader.team_name)+'</strong></p>';
 }else{
  const leader=mapState.leader_after_match_18;
  $('smashMapSelection').innerHTML='<div class="eyebrow">MATCH 18 LEADER · MAP PICKER</div><h3>'+esc(leader.team_name)+'</h3><p>'+leader.total_points+' points after Match 18.</p><p class="muted">Waiting for the Erangel Showmatch winner, their map ban and the leader’s Match 19 map selection to be entered by an admin.</p>';
 }
}

async function loadTeamDirectory(){
 const meta=$('teamDirectoryMeta'),grid=$('teamDirectoryGrid');
 if(!meta||!grid)return;
 const teams=[
  'AK Gold Esports','Sharper Esports','4Thrives','The MongolZ','Aurora Gaming',
  '4K Esports','iKURD Esports','S2G Esports','Gaming Stars Esports','Hustler Crew',
  'Wolves Esports','RoW Esports','XForce Rejects','All Gamers','Team SouL',
  'Nongshim RedForce','Bigetron by Vitality','eArena','Team Flash','Horaa Esports',
  'Trained to Kill','OLD NOT','GOAT TEAM','AlUla Club Esports','Geekay Esports',
  'Nigma Galaxy','R8 Esports','Selibon Esports','BUF Esports','BRX MSM Esports',
  '3Boars Gaming','FURIA Esports','Alpha7 Esports','Weibo Gaming','LGD Gaming',
  'DRX','VARREL','Dplus KIA','ULF Esports'
 ];
 const logoFiles={
  'AK Gold Esports':'AK_Gold_Esports_allmode.png',
  'Sharper Esports':'900px-Sharper_Esports_2026_full_allmode.png',
  '4Thrives':'900px-4thrives_gold_logo_2024_allmode.png',
  'The MongolZ':'900px-The_MongolZ_2024_03_allmode.png',
  'Aurora Gaming':'900px-Aurora_Gaming_2025_full_allmode.png',
  '4K Esports':'900px-4K_Esports_allmode.png',
  'iKURD Esports':'900px-IKURD_Esports_2025_allmode.png',
  'S2G Esports':'51px-S2G_Esports_allmode.png',
  'Wolves Esports':'87px-Wolves_Esports_allmode.png',
  'RoW Esports':'91px-RoW_Esports_2025_allmode.png',
  'XForce Rejects':'117px-XFORCE_REJECTS_darkmode.png',
  'All Gamers':'58px-All_Gamers_allmode.png',
  'Team SouL':'61px-Team_Soul_2019_allmode.png',
  'Nongshim RedForce':'56px-Nongshim_RedForce_allmode.png',
  'Bigetron by Vitality':'89px-Bigetron_by_Vitality_full_darkmode.png',
  'eArena':'75px-EArena_2022_allmode.png',
  'Team Flash':'84px-Team_Flash_allmode.png',
  'Horaa Esports':'77px-Horaa_Esports_darkmode.png',
  'Trained to Kill':'86px-Trained_To_Kill_2020_darkmode.png',
  'OLD NOT':'74px-OLD_NOT_2024_darkmode.png',
  'GOAT TEAM':'83px-GOAT_TEAM_allmode.png',
  'AlUla Club Esports':'60px-Al-Ula_allmode.png',
  'Geekay Esports':'101px-Geekay_Esports_2024_allmode.png',
  'Nigma Galaxy':'75px-Nigma_Galaxy_darkmode.png',
  'R8 Esports':'89px-R8_Esports_2022_darkmode.png',
  'Selibon Esports':'93px-Selibon_Esports_allmode.png',
  'BUF Esports':'67px-BUF_Esports_allmode.png',
  'BRX MSM Esports':'72px-BRX_MSM_Esports_allmode.png',
  '3Boars Gaming':'59px-Boars_Gaming_allmode.png',
  'FURIA Esports':'77px-FURIA_Esports_allmode.png',
  'Alpha7 Esports':'109px-A7_eSports_darkmode.png',
  'Weibo Gaming':'93px-Weibo_allmode.png',
  'LGD Gaming':'75px-LGD_Gaming_Dec_2019_allmode.png',
  'DRX':'75px-DRX_2026_darkmode.png',
  'VARREL':'74px-VARREL_2026_allmode.png',
  'Dplus KIA':'150px-Dplus_darkmode.png',
  'ULF Esports':'102px-ULF_Esports_darkmode.png'
 };
 const base='/static/images/teams/';
 const logoCount=Object.keys(logoFiles).length;
 meta.textContent=teams.length+' teams · '+logoCount+' team logos connected · 32 × 32 px';
 grid.innerHTML=teams.map(name=>{
  const file=logoFiles[name];
  const visual=file
   ?'<img class="team-directory-logo" src="'+base+encodeURIComponent(file).replace(/%2F/g,'/')+'" alt="'+esc(name)+' logo" loading="lazy">'
   :'<span class="team-directory-mark">'+esc(name.slice(0,1))+'</span>';
  return '<article class="team-directory-card">'+visual+'<strong>'+esc(name)+'</strong></article>';
 }).join('');
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('tournamentSelect').addEventListener('change',loadBoard);loadTournaments();loadTeamDirectory();