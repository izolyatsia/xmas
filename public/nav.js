/*
 * Page transitions between years (native cross-document View Transitions).
 * Loaded as a classic, render-blocking script in <head> so the `pagereveal`
 * listener is registered before the first frame of the new page.
 * Browsers without support simply do a normal page load.
 */
(function () {
  function yearOf(url) {
    var m = /\/(\d{4})\/(?:index\.html)?(?:[?#].*)?$/.exec(url || '');
    return m ? parseInt(m[1], 10) : 0; // 0 = home page
  }

  // Slide direction: later year => forward, earlier year (or home) => backward.
  window.addEventListener('pagereveal', function (e) {
    if (!e.viewTransition) return;
    // Navigation API where available; document.referrer otherwise (older Safari)
    var fromUrl = window.navigation && navigation.activation && navigation.activation.from
      ? navigation.activation.from.url
      : document.referrer;
    if (!fromUrl || fromUrl.indexOf(location.origin) !== 0) return;
    var a = yearOf(fromUrl);
    var b = yearOf(location.href);
    if (!a || !b) {
      e.viewTransition.types.add('fade');
    } else if (b > a) {
      e.viewTransition.types.add('forward');
    } else if (b < a) {
      e.viewTransition.types.add('backward');
    }
  });

  // Prefetch year pages on hover/focus so the switch feels instant.
  if (window.HTMLScriptElement && HTMLScriptElement.supports &&
      HTMLScriptElement.supports('speculationrules')) {
    var s = document.createElement('script');
    s.type = 'speculationrules';
    s.textContent = JSON.stringify({
      prefetch: [{
        where: { selector_matches: '.cont a, .year-arrow, a.card' },
        eagerness: 'moderate'
      }]
    });
    document.head.appendChild(s);
  }
})();

// Phones: the nav is a horizontally scrolling row; bring the current year into view.
document.addEventListener('DOMContentLoaded', function () {
  var ul = document.querySelector('.cont ul');
  var a = ul && ul.querySelector('a.active');
  if (!ul || !a || ul.scrollWidth <= ul.clientWidth) return;
  ul.scrollLeft = a.offsetLeft - ul.offsetLeft - (ul.clientWidth - a.offsetWidth) / 2;
});
