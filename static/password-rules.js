// Odhacza na żywo wymogi hasła (lista .pw-rules z registration/_password_rules.html).
// Wymogi sprawdza serwer (widok password_check) tymi samymi walidatorami, co przy zapisie formularza,
// więc lista zawsze zgadza się z tym, co Django potem przyjmie albo odrzuci.
(function () {
  document.querySelectorAll(".pw-rules").forEach(function (box) {
    var pw = document.getElementById(box.dataset.password);
    var pw2 = document.getElementById(box.dataset.confirm);
    if (!pw || !pw2) return;
    var form = pw.form;
    var csrf = form.querySelector("[name=csrfmiddlewaretoken]");
    var rules = box.querySelectorAll("li[data-i]");
    var match = box.querySelector("li[data-match]");
    var timer = null;
    var seq = 0;

    function value(name) {
      var el = form.querySelector("[name=" + name + "]");
      return el ? el.value : (box.dataset[name] || "");
    }

    // state: true = spełniony, false = niespełniony, null = jeszcze nic nie wpisano
    function mark(li, state) {
      li.classList.toggle("ok", state === true);
      li.classList.toggle("bad", state === false);
    }

    function checkMatch() {
      mark(match, pw2.value ? pw2.value === pw.value : null);
    }

    function check() {
      checkMatch();
      if (!pw.value) {
        rules.forEach(function (li) { mark(li, null); });
        return;
      }
      var mine = ++seq;
      var body = new URLSearchParams({ password: pw.value, username: value("username"), email: value("email") });
      fetch(box.dataset.checkUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf ? csrf.value : "" },
        body: body,
        credentials: "same-origin"
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (data) {
          if (mine !== seq) return; // przyszła już odpowiedź na nowszy tekst
          rules.forEach(function (li, i) { mark(li, data.ok[i]); });
        })
        .catch(function () { /* bez sieci lista zostaje jak była – serwer i tak sprawdzi przy wysłaniu */ });
    }

    function later() {
      clearTimeout(timer);
      timer = setTimeout(check, 250);
    }

    pw.addEventListener("input", later);
    pw2.addEventListener("input", checkMatch);
    ["username", "email"].forEach(function (name) {
      var el = form.querySelector("[name=" + name + "]");
      if (el) el.addEventListener("input", later); // na wypadek walidatorów zależnych od nazwy/e-maila
    });
    if (pw.value) check();
  });
})();
