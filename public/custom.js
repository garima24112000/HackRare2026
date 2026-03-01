/* ══════════════════════════════════════════════════════════
   Diagnostic Copilot — Custom JS (Portal-Based Dashboard)
   ══════════════════════════════════════════════════════════
   Strategy:
   Chainlit's React DOM applies CSS `transform` on ancestor
   containers, which breaks `position: fixed` on descendants.
   To work around this, we MOVE our custom screen elements
   (.screen-input, .screen-dash, .patient-load-card) out of
   Chainlit's DOM tree and directly into <body>. The CSS
   class `.dc-portal` then gives them fixed viewport coverage.
   ══════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  var SCREEN_SEL = '.screen-input, .screen-dash, .patient-load-card';
  var portalEl = null;

  /* ── Accordion toggle for differential diagnosis ──── */
  function toggleDA(card) {
    var siblings = card.parentElement ? card.parentElement.querySelectorAll('.da.open') : [];
    siblings.forEach(function (c) { if (c !== card) c.classList.remove('open'); });
    card.classList.toggle('open');
  }

  /* ── Select patient in the input screen ──────────── */
  function selectPatient(btn) {
    var grid = btn.closest('.patient-grid');
    if (grid) grid.querySelectorAll('.pt-btn').forEach(function (b) { b.classList.remove('sel'); });
    btn.classList.add('sel');
  }

  /* ── Submit text to Chainlit's own composer ──────── */
  function submitToChat(text) {
    if (!text || !text.trim()) return;

    /* Find Chainlit's textarea — skip our .hpo-input-field and anything inside our portal */
    var input = null;
    var allTA = document.querySelectorAll('textarea');
    for (var i = 0; i < allTA.length; i++) {
      if (!allTA[i].classList.contains('hpo-input-field') &&
          !allTA[i].closest('.dc-portal') &&
          !allTA[i].closest('.screen-input')) {
        input = allTA[i];
        break;
      }
    }
    if (!input) return;

    /* React-compatible value setter */
    var nativeSet =
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value') ||
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    if (nativeSet && nativeSet.set) {
      nativeSet.set.call(input, text);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      setTimeout(function () {
        input.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
        }));
      }, 100);
    }
  }

  /* ═══════════════════════════════════════════════════════
     PORTAL — move screen elements to <body> to escape
     Chainlit's transform containment block
     ═══════════════════════════════════════════════════════ */
  function portalUpdate() {
    /* Gather all screen candidates anywhere in the DOM */
    var candidates = document.querySelectorAll(SCREEN_SEL);
    if (candidates.length === 0) return;

    /* Pick the LAST candidate that is NOT our current portal */
    var target = null;
    for (var i = candidates.length - 1; i >= 0; i--) {
      if (candidates[i] !== portalEl) {
        target = candidates[i];
        break;
      }
    }

    /* No new screen found — current portal is still valid */
    if (!target) return;

    /* Already portaled (direct child of body with dc-portal)? adopt reference */
    if (target.parentElement === document.body && target.classList.contains('dc-portal')) {
      portalEl = target;
      document.body.classList.add('dc-screen-active');
      return;
    }

    /* Tear down previous portal */
    if (portalEl) {
      portalEl.remove();
      portalEl = null;
    }

    /* Move the element to <body> — this preserves event listeners & form state */
    target.classList.add('dc-portal');
    document.body.appendChild(target);
    portalEl = target;
    document.body.classList.add('dc-screen-active');

    /* Bind interactive elements on the freshly portaled node */
    bindInteractiveElements(portalEl);
  }

  /* ── Bind interactive elements ────────────────────── */
  function bindInteractiveElements(root) {
    if (!root || !root.querySelectorAll) return;

    /* Differential accordion: .da-row click → toggle parent .da */
    root.querySelectorAll('.da-row').forEach(function (row) {
      if (!row.dataset.bound) {
        row.dataset.bound = '1';
        row.addEventListener('click', function () {
          toggleDA(row.closest('.da'));
        });
      }
    });

    /* Patient card click → select */
    root.querySelectorAll('.pt-btn').forEach(function (btn) {
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', function () {
          selectPatient(btn);
        });
      }
    });

    /* Run button → submit HPO text or load selected patient */
    root.querySelectorAll('.run-btn').forEach(function (btn) {
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', function () {
          /* Check for manual HPO text first */
          var ta = portalEl ? portalEl.querySelector('.hpo-input-field') : null;
          if (ta && ta.value.trim()) {
            submitToChat(ta.value.trim());
            return;
          }

          /* Otherwise send patient selection as a chat message */
          var selected = portalEl ? portalEl.querySelector('.pt-btn.sel') : null;
          if (selected) {
            var idx = selected.dataset.patientIndex;
            submitToChat('load_patient:' + idx);
          }
        });
      }
    });

    /* Assess chip click → inject HPO term into chat */
    root.querySelectorAll('.ac').forEach(function (chip) {
      if (!chip.dataset.bound) {
        chip.dataset.bound = '1';
        chip.addEventListener('click', function () {
          var term = chip.dataset.hpoId;
          var label = chip.dataset.hpoLabel;
          if (term) submitToChat('Assess for: ' + term + ' (' + label + ')');
        });
      }
    });

    /* Back button → reload to reset */
    root.querySelectorAll('.back-btn').forEach(function (btn) {
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', function () { window.location.reload(); });
      }
    });
  }

  /* ── MutationObserver: react to new Chainlit messages ── */
  var observer = new MutationObserver(function (mutations) {
    var check = false;
    mutations.forEach(function (m) {
      m.addedNodes.forEach(function (n) { if (n.nodeType === 1) check = true; });
    });
    if (check) setTimeout(portalUpdate, 200);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  /* ── Periodic fallback (catches late renders) ─────── */
  setInterval(portalUpdate, 2000);

  /* ── Initial checks on page load ─────────────────── */
  setTimeout(portalUpdate, 300);
  setTimeout(portalUpdate, 1000);
  setTimeout(portalUpdate, 2500);

})();
