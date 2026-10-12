(function () {
  if (window.outreachMailEditorLoaded) {
    return;
  }
  window.outreachMailEditorLoaded = true;
  document.documentElement.classList.add("js");

  function closeMenus(except) {
    document.querySelectorAll("[data-outreach-variable-toggle]").forEach(function (toggle) {
      var menu = toggle.parentElement.querySelector(".menu");
      if (menu === except) {
        return;
      }
      menu.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    });
  }

  function editorFor(toolbar) {
    return document.querySelector('trix-editor[toolbar="' + toolbar.id + '"]');
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-outreach-variable-toggle]");
    if (toggle) {
      var menu = toggle.parentElement.querySelector(".menu");
      closeMenus(menu);
      menu.hidden = !menu.hidden;
      toggle.setAttribute("aria-expanded", String(!menu.hidden));
      return;
    }
    var item = event.target.closest("[data-trix-variable], [data-trix-tag]");
    if (item) {
      var editor = editorFor(item.closest("trix-toolbar"));
      if (editor) {
        editor.focus();
        editor.editor.insertString(
          item.dataset.trixTag
            ? "{% " + item.dataset.trixTag + " %}"
            : "{{ " + item.dataset.trixVariable + " }}"
        );
      }
      closeMenus(null);
      return;
    }
    closeMenus(null);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeMenus(null);
    }
  });

  document.addEventListener("trix-file-accept", function (event) {
    event.preventDefault();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.target.tagName !== "INPUT") {
      return;
    }
    var saveBlock = event.target.closest("[data-outreach-save-block]");
    if (!saveBlock) {
      return;
    }
    event.preventDefault();
    saveBlock.querySelector("[data-outreach-save-button]").click();
  });

  document.addEventListener("change", function (event) {
    var select = event.target.closest("[data-outreach-auto-submit]");
    if (select && select.form) {
      select.form.requestSubmit();
    }
  });
})();
