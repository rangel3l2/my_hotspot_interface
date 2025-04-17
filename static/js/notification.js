const notificationSound = new Audio('/static/sound/notification.mp3');

function showNotification(message) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.style.display = 'block';
    
    try {
        notificationSound.play().catch(error => {
            console.log("Erro ao tocar som:", error);
        });
    } catch (error) {
        console.log("Erro ao tocar som:", error);
    }

    setTimeout(() => {
        notification.style.display = 'none';
    }, 5000);
}
