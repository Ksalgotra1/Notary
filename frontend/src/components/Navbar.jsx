import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Shield, Wand2, Library, Activity } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();

  // Hide main app navbar on public verification portal route
  if (location.pathname.startsWith('/verify/')) {
    return null;
  }

  return (
    <header className="navbar">
      <NavLink to="/" className="navbar-brand">
        <div className="navbar-brand-icon">
          <Shield style={{ width: 18, height: 18, strokeWidth: 2.2 }} />
        </div>
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
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Wand2 style={{ width: 14, height: 14 }} />
            <span>Generate</span>
          </span>
        </NavLink>
        <NavLink
          to="/library"
          className={({ isActive }) =>
            `navbar-link ${isActive ? 'active' : ''}`
          }
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Library style={{ width: 14, height: 14 }} />
            <span>Library</span>
          </span>
        </NavLink>
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `navbar-link ${isActive ? 'active' : ''}`
          }
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Activity style={{ width: 14, height: 14 }} />
            <span>Dashboard</span>
          </span>
        </NavLink>
      </nav>
    </header>
  );
}
