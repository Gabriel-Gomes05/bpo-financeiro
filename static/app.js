// JS mínimo para interações que o HTMX não cobre

// Fecha flash messages ao clicar
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-dismiss]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      btn.closest("[data-flash]").remove();
    });
  });
});
