import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';

export default function Navbar() {
  const location = useLocation();

  // Hide main app navbar on public verification portal route
  if (location.pathname.startsWith('/verify/')) {
    return null;
  }

  return (
    <header className="navbar">
      <NavLink to="/" className="navbar-brand">
        <div className="navbar-brand-icon">🛡️</div>
        <span>Notary</span>
      </NavLink>
      <nav className="navbar-links">
        <NavLink
          to="/"
          className={({ isActive }) =>
            `navbar-link ${isActive ? 'active' : ''}`
          }
          end
        >
          Generate
        </NavLink>
        <NavLink
          to="/library"
          className={({ isActive }) =>
            `navbar-link ${isActive ? 'active' : ''}`
          }
        >
          Library
        </NavLink>
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `navbar-link ${isActive ? 'active' : ''}`
          }
        >
          ⚡ Dashboard
        </NavLink>
      </nav>
    </header>
  );
}
