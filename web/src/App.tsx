import { useState } from 'react';
import { getRole, getToken, setSession } from './lib/api';
import { Login } from './pages/Login';
import { Accounts } from './pages/Accounts';
import { Images } from './pages/Images';
import { Dispatch } from './pages/Dispatch';
import { Tasks } from './pages/Tasks';
import { Admin } from './pages/Admin';

type Tab = 'accounts' | 'images' | 'dispatch' | 'tasks' | 'admin';

const TABS: { key: Tab; label: string; adminOnly?: boolean }[] = [
  { key: 'accounts', label: '계정·가맹점' },
  { key: 'images', label: '이미지' },
  { key: 'dispatch', label: '배포' },
  { key: 'tasks', label: '작업 현황' },
  { key: 'admin', label: '관리자', adminOnly: true },
];

export function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [tab, setTab] = useState<Tab>('accounts');
  const role = getRole();

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  function logout() {
    setSession(null);
    setAuthed(false);
  }

  const visibleTabs = TABS.filter((t) => !t.adminOnly || role === 'admin');

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">📍 SmartPlace Cloud</div>
        <nav className="tabs">
          {visibleTabs.map((t) => (
            <button
              key={t.key}
              className={`tab ${tab === t.key ? 'tab--active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar__right">
          <span className="role-badge">{role}</span>
          <button className="btn btn--ghost" onClick={logout}>
            로그아웃
          </button>
        </div>
      </header>

      <main className="content">
        {tab === 'accounts' && <Accounts />}
        {tab === 'images' && <Images />}
        {tab === 'dispatch' && <Dispatch />}
        {tab === 'tasks' && <Tasks />}
        {tab === 'admin' && role === 'admin' && <Admin />}
      </main>
    </div>
  );
}
