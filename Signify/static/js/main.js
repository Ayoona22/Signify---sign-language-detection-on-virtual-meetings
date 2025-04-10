// Add smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
    });
});

// Add click handlers for buttons
document.querySelector('.primary-btn').addEventListener('click', () => {
    // Redirect to meeting room or sign up page
    window.location.href = '/meeting';
});

document.querySelector('.secondary-btn').addEventListener('click', () => {
    // Scroll to features section
    document.querySelector('#features').scrollIntoView({
        behavior: 'smooth'
    });
}); 