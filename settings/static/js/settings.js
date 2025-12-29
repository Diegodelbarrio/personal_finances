document.addEventListener('DOMContentLoaded', function() {
    // Buscamos todas las barras de progreso que tengan la variable definida
    const bars = document.querySelectorAll('.progress-bar');
    
    bars.forEach(bar => {
        // Obtenemos el valor de la variable del padre
        const progress = bar.parentElement.style.getPropertyValue('--progress');
        // Aplicamos un pequeño delay para que se vea la animación
        setTimeout(() => {
            bar.style.width = progress;
        }, 100);
    });
});

document.addEventListener('DOMContentLoaded', function () {
    var toastElList = [].slice.call(document.querySelectorAll('.toast'))
    var toastList = toastElList.map(function (toastEl) {
        var t = new bootstrap.Toast(toastEl, { delay: 3000 });
        t.show();
        return t;
    });
});