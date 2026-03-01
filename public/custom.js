/* ── Diagnostic Copilot — Custom JS ─────────────────── */

/* Accordion toggle for differential diagnosis cards */
function toggleCard(card) {
  card.classList.toggle('open');
}

/* MutationObserver: attach click handlers to dynamically injected elements */
var observer = new MutationObserver(function (mutations) {
  mutations.forEach(function (m) {
    m.addedNodes.forEach(function (node) {
      if (node.querySelectorAll) {
        /* Differential accordion headers */
        node.querySelectorAll('.dc-header').forEach(function (hdr) {
          if (!hdr.dataset.bound) {
            hdr.dataset.bound = '1';
            hdr.addEventListener('click', function () {
              toggleCard(hdr.closest('.diff-card'));
            });
          }
        });

        /* Assess chip click → inject HPO term into chat input */
        node.querySelectorAll('.assess-chip').forEach(function (chip) {
          if (!chip.dataset.bound) {
            chip.dataset.bound = '1';
            chip.addEventListener('click', function () {
              var term = chip.dataset.hpoId;
              var label = chip.dataset.hpoLabel;
              if (term) {
                var input = document.querySelector('textarea, input[type="text"]');
                if (input) {
                  var nativeSet = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                  );
                  if (!nativeSet) {
                    nativeSet = Object.getOwnPropertyDescriptor(
                      window.HTMLInputElement.prototype, 'value'
                    );
                  }
                  if (nativeSet && nativeSet.set) {
                    nativeSet.set.call(input, 'Assess for: ' + term + ' (' + label + ')');
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                  }
                }
              }
            });
          }
        });

        /* Patient selector card click → find and click corresponding action button */
        node.querySelectorAll('.patient-select-card').forEach(function (card) {
          if (!card.dataset.bound) {
            card.dataset.bound = '1';
            card.addEventListener('click', function () {
              var idx = parseInt(card.dataset.patientIndex, 10);
              /* Find the Chainlit action buttons and click the matching one */
              var buttons = document.querySelectorAll('button[id^="action"]');
              if (buttons[idx]) {
                buttons[idx].click();
              }
            });
          }
        });
      }
    });
  });
});
observer.observe(document.body, { childList: true, subtree: true });

/* Override input placeholder */
var placeholderInterval = setInterval(function () {
  var input = document.querySelector('textarea, input[type="text"]');
  if (input) {
    input.placeholder = 'Paste a clinical note, enter HP: terms, or select a patient\u2026';
    clearInterval(placeholderInterval);
  }
}, 500);
