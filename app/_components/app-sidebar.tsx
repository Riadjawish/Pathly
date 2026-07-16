import Image from "next/image";
import Link from "next/link";
import { BookOpen, CircleHelp, Home, Sparkles, UserRound } from "lucide-react";

export type AppSection = "home" | "subjects" | "account" | "support";

const links = [
  { id: "home" as const, href: "/", label: "Home", icon: Home },
  { id: "subjects" as const, href: "/subjects", label: "Subjects", icon: BookOpen },
  { id: "account" as const, href: "/account", label: "Account", icon: UserRound },
  { id: "support" as const, href: "/support", label: "Support", icon: CircleHelp },
];

export function AppSidebar({ active }: { active: AppSection }) {
  return <aside className="app-sidebar">
    <Link className="pathly-logo" href="/"><Image src="/pathly-logo.svg" alt="Pathly" width={42} height={42}/><span>pathly</span></Link>
    <nav aria-label="Main navigation">{links.map(({ id, href, label, icon: Icon }) => <Link className={active === id ? "active" : ""} href={href} key={id}><Icon /><span>{label}</span></Link>)}</nav>
    <div className="app-sidebar-card"><Sparkles /><b>Keep moving forward</b><p>Your next study step is waiting.</p></div>
  </aside>;
}

export function AppMobileNav({ active }: { active: AppSection }) {
  return <nav className="app-mobile-nav" aria-label="Mobile navigation">{links.map(({ id, href, label, icon: Icon }) => <Link className={active === id ? "active" : ""} href={href} key={id} aria-label={label}><Icon /></Link>)}</nav>;
}
