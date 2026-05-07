/**
 * avatar_menu.js — Close the avatar dropdown when clicking outside it.
 *
 * Dispatches AvatarMenuState.close to the Reflex state when the user
 * clicks anywhere outside the .nav-rail-avatar-menu or .nav-rail-avatar.
 * Loaded once at app boot via head_components in brijkillian_stack.py.
 */
document.addEventListener('click', function (e) {
  var menu   = document.querySelector('.nav-rail-avatar-menu');
  var avatar = document.querySelector('.nav-rail-avatar');
  if (!menu) return;                        // dropdown is closed — nothing to do
  if (avatar && avatar.contains(e.target)) return;  // avatar toggle — let Reflex handle
  if (menu.contains(e.target)) return;     // click inside menu — let item handle
  // Click is outside — close via Reflex dispatch
  window._reflexDispatch &&
    window._reflexDispatch('avatar_menu_state.close', {});
});
