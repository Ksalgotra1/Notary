import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Shield,
  LayoutDashboard,
  Wand2,
  Library,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export default function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('sidebar_collapsed') === 'true';
  });

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('sidebar_collapsed', String(next));
      return next;
    });
  };

  // Hide main app sidebar on public verification portal route
  if (location.pathname.startsWith('/verify/')) {
    return null;
  }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Header & Collapse Toggle */}
      <div className="sidebar-header">
        <NavLink to="/" className="sidebar-brand" title="Notary">
          <div className="sidebar-brand-icon">
            <Shield style={{ width: 20, height: 20, strokeWidth: 2.2 }} />
          </div>
          {!collapsed && <span className="sidebar-brand-text">Notary</span>}
        </NavLink>

        <button
          className="sidebar-toggle-btn"
          onClick={toggleSidebar}
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          aria-label={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? (
            <ChevronRight style={{ width: 16, height: 16 }} />
          ) : (
            <ChevronLeft style={{ width: 16, height: 16 }} />
          )}
        </button>
      </div>

      {/* Main Navigation Links */}
      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? 'active' : ''}`
          }
          title={collapsed ? 'Dashboard' : ''}
        >
          <LayoutDashboard className="sidebar-icon" />
          {!collapsed && <span>Dashboard</span>}
        </NavLink>

        <NavLink
          to="/"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? 'active' : ''}`
          }
          end
          title={collapsed ? 'Generate' : ''}
        >
          <Wand2 className="sidebar-icon" />
          {!collapsed && <span>Generate</span>}
        </NavLink>

        <NavLink
          to="/library"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? 'active' : ''}`
          }
          title={collapsed ? 'Library' : ''}
        >
          <Library className="sidebar-icon" />
          {!collapsed && <span>Library</span>}
        </NavLink>
      </nav>

      {/* Footer Info */}
      <div className="sidebar-footer">
        <div className="sidebar-footer-card" title={collapsed ? 'B2 Object Lock Active' : ''}>
          <ShieldCheck style={{ width: 18, height: 18, color: '#11ff99', flexShrink: 0 }} />
          {!collapsed && (
            <div className="sidebar-footer-text">
              <div className="sidebar-footer-title">B2 Object Lock</div>
              <div className="sidebar-footer-sub">Immutability Active</div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
