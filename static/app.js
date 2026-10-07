document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.add-cart');
  if (!btn) return;
  e.preventDefault();
  btn.disabled = true;
  try {
    const r = await fetch('/cart/add/' + btn.dataset.id, {method:'POST'});
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || 'حدث خطأ');
    document.querySelectorAll('.badge').forEach(x => x.textContent = data.count);
    const old=btn.textContent; btn.textContent='تمت الإضافة ✓';
    setTimeout(()=>{btn.textContent=old;btn.disabled=false},900);
  } catch(err) { alert(err.message); btn.disabled=false; }
});
