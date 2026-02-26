/*
  TabNav.jsx — Horizontal tab navigation.
*/
import React from 'react';

export default function TabNav({ tabs, active, onChange }) {
  return (
    <div className="tab-nav">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab-btn ${active === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
