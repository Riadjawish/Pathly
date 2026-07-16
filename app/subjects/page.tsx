"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { createSubjectId, useSubjects } from "../_hooks/use-subjects";
import { AppMobileNav, AppSidebar } from "../_components/app-sidebar";
import {
  ArrowLeft, ArrowRight, Check, Flame, Pencil, Plus, Search,
  Trash2, Upload, X,
} from "lucide-react";

const subjectEmojis = [
  "📚", "📖", "📝", "🎓", "🧠", "🔬", "🧪", "🧬",
  "🌱", "🌍", "🏛️", "⚛️", "📐", "➗", "💻", "🤖",
  "🎨", "🎵", "🗣️", "💼", "⚖️", "🩺", "🚀", "✨",
];

const subjectPalettes = [
  { tone: "green", label: "Forest", color: "#2f9f4c" },
  { tone: "blue", label: "Ocean", color: "#4d76df" },
  { tone: "purple", label: "Violet", color: "#7754ce" },
  { tone: "orange", label: "Sunset", color: "#ef713a" },
  { tone: "yellow", label: "Golden", color: "#dfa52f" },
  { tone: "indigo", label: "Cosmic", color: "#496fd2" },
  { tone: "pink", label: "Berry", color: "#d95e8c" },
];

function detectEmojiTone(emoji: string) {
  const canvas = document.createElement("canvas");
  canvas.width = 48;
  canvas.height = 48;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return "green";
  context.font = '36px "Apple Color Emoji", "Segoe UI Emoji", sans-serif';
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(emoji || "✨", 24, 25);
  const pixels = context.getImageData(0, 0, 48, 48).data;
  let red = 0, green = 0, blue = 0, weight = 0;
  for (let index = 0; index < pixels.length; index += 4) {
    const alpha = pixels[index + 3] / 255;
    const max = Math.max(pixels[index], pixels[index + 1], pixels[index + 2]);
    const min = Math.min(pixels[index], pixels[index + 1], pixels[index + 2]);
    const saturation = max - min;
    if (alpha < .2 || saturation < 18) continue;
    const pixelWeight = alpha * (1 + saturation / 255);
    red += pixels[index] * pixelWeight;
    green += pixels[index + 1] * pixelWeight;
    blue += pixels[index + 2] * pixelWeight;
    weight += pixelWeight;
  }
  if (!weight) return "green";
  const average = [red / weight, green / weight, blue / weight];
  const targets: Record<string, number[]> = { green: [55, 165, 80], blue: [65, 125, 220], purple: [130, 85, 205], orange: [235, 115, 50], yellow: [220, 170, 45], indigo: [70, 95, 195], pink: [215, 85, 135] };
  return Object.entries(targets).sort(([, first], [, second]) => first.reduce((sum, value, i) => sum + (value - average[i]) ** 2, 0) - second.reduce((sum, value, i) => sum + (value - average[i]) ** 2, 0))[0][0];
}

export default function SubjectsPage() {
  const [subjects, setSubjects] = useSubjects();
  const [query, setQuery] = useState("");
  const [newName, setNewName] = useState("");
  const [selectedEmoji, setSelectedEmoji] = useState("📚");
  const [selectedTone, setSelectedTone] = useState("yellow");
  const [showCreator, setShowCreator] = useState(false);
  const [showAllEmojis, setShowAllEmojis] = useState(false);
  const [editing, setEditing] = useState<{ index: number; name: string; emoji: string; tone: string } | null>(null);
  const [deleting, setDeleting] = useState<{ index: number; name: string } | null>(null);

  const filtered = useMemo(
    () => subjects.map((subject, index) => ({ subject, index })).filter(({ subject }) => subject.name.toLowerCase().includes(query.toLowerCase())),
    [query, subjects],
  );

  function createSubject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setSubjects((items) => [...items, { id: createSubjectId(name), name, short: name, description: "Your custom study journey", topics: 0, progress: 0, icon: selectedEmoji, tone: selectedTone }]);
    setNewName("");
    setSelectedEmoji("📚");
    setSelectedTone("yellow");
    setShowAllEmojis(false);
    setShowCreator(false);
  }

  function saveSubject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || !editing.name.trim()) return;
    setSubjects((items) => items.map((subject, index) => index === editing.index ? { ...subject, name: editing.name.trim(), short: editing.name.trim(), icon: editing.emoji, tone: editing.tone } : subject));
    setEditing(null);
  }

  function deleteSubject() {
    if (!deleting) return;
    setSubjects((items) => items.filter((_, index) => index !== deleting.index));
    setDeleting(null);
  }

  return (
    <main className="subjects-page">
      <AppSidebar active="subjects" />

      <section className="subjects-content">
        <header className="subjects-header">
          <Link href="/" aria-label="Back to dashboard"><ArrowLeft /></Link>
          <div><span className="micro-label dark">YOUR LEARNING LIBRARY</span><h1>What are you studying?</h1><p>Choose a subject to continue its mastery journey.</p></div>
          <div className="subject-streak"><Flame /><b>12</b><span>day streak</span></div>
        </header>

        <div className="subject-toolbar">
          <label><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your subjects" />{query && <button onClick={() => setQuery("")} aria-label="Clear search"><X /></button>}</label>
          <button onClick={() => setShowCreator(true)}><Plus /> New subject</button>
        </div>

        <section className="subject-card-grid" aria-label="Subjects">
          {filtered.map(({ subject, index }) => (
            <article className={`library-card ${subject.tone}`} key={`${subject.name}-${index}`}>
              <div className="card-manage"><button onClick={() => setEditing({ index, name: subject.name, emoji: subject.icon, tone: subject.tone })} aria-label={`Edit ${subject.name}`}><Pencil /></button><button onClick={() => setDeleting({ index, name: subject.name })} aria-label={`Delete ${subject.name}`}><Trash2 /></button></div>
              <div className="library-art"><span>{subject.icon}</span><div className="library-ring" style={{ background: `conic-gradient(#fff ${subject.progress * 3.6}deg,rgba(255,255,255,.25) 0)` }}><i>{subject.progress}%</i></div></div>
              <div className="library-info"><span>{subject.topics} topics</span><h2>{subject.name}</h2><p>{subject.description}</p></div>
              <div className="library-actions"><Link href={`/subjects/${subject.id}`}>Open workspace <ArrowRight /></Link><Link className="upload-link" href={`/subjects/${subject.id}#materials`} aria-label={`Upload materials for ${subject.name}`}><Upload /></Link></div>
            </article>
          ))}
          {filtered.length === 0 && <div className="empty-subjects"><Search /><h2>No subjects found</h2><p>Try another search or create a new subject.</p></div>}
        </section>

      </section>

      {showCreator && <div className="creator-backdrop" onMouseDown={() => setShowCreator(false)}><form className="creator-modal" onSubmit={createSubject} onMouseDown={(event) => event.stopPropagation()}><button type="button" className="modal-close" onClick={() => setShowCreator(false)} aria-label="Close"><X /></button><span className={`creator-icon emoji-preview theme-${selectedTone}`}>{selectedEmoji}</span><span className="micro-label dark">NEW MASTERY JOURNEY</span><h2>Create a subject</h2><p>The theme is matched to your emoji automatically, and you can customize it.</p><fieldset className="emoji-picker"><legend>Choose an icon</legend><div>{subjectEmojis.map((emoji) => <button type="button" className={selectedEmoji === emoji ? "selected" : ""} onClick={() => { setSelectedEmoji(emoji); setSelectedTone(detectEmojiTone(emoji)); }} key={emoji} aria-label={`Use ${emoji} icon`}>{emoji}</button>)}<button type="button" className="all-emoji-button" onClick={() => setShowAllEmojis((open) => !open)} aria-label="Choose a custom emoji">•••</button></div>{showAllEmojis && <label className="all-emoji-input"><span>Custom emoji</span><input value={selectedEmoji} onChange={(event) => { setSelectedEmoji(event.target.value); setSelectedTone(detectEmojiTone(event.target.value)); }} maxLength={14} placeholder="😀" /><small>The closest theme color is selected automatically.</small></label>}</fieldset><fieldset className="theme-picker"><legend>Course background</legend><div>{subjectPalettes.map((palette) => <button type="button" className={selectedTone === palette.tone ? "selected" : ""} onClick={() => setSelectedTone(palette.tone)} key={palette.tone} aria-label={`Use ${palette.label} theme`}><i style={{ background: palette.color }}/><span>{palette.label}</span></button>)}</div></fieldset><label>Subject name<input autoFocus value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="e.g. Organic Chemistry" maxLength={30} /></label><button type="submit" className="create-button">Create subject <ArrowRight /></button></form></div>}
      {editing && <div className="creator-backdrop" onMouseDown={() => setEditing(null)}><form className="creator-modal" onSubmit={saveSubject} onMouseDown={(event) => event.stopPropagation()}><button type="button" className="modal-close" onClick={() => setEditing(null)} aria-label="Close"><X /></button><span className={`creator-icon emoji-preview theme-${editing.tone}`}>{editing.emoji}</span><span className="micro-label dark">EDIT SUBJECT</span><h2>Update your subject</h2><p>Change its name, emoji or course background theme.</p><fieldset className="emoji-picker"><legend>Choose an icon</legend><div>{subjectEmojis.map((emoji) => <button type="button" className={editing.emoji === emoji ? "selected" : ""} onClick={() => setEditing({ ...editing, emoji, tone: detectEmojiTone(emoji) })} key={emoji} aria-label={`Use ${emoji} icon`}>{emoji}</button>)}<button type="button" className="all-emoji-button" onClick={() => setShowAllEmojis((open) => !open)} aria-label="Choose a custom emoji">•••</button></div>{showAllEmojis && <label className="all-emoji-input"><span>Custom emoji</span><input value={editing.emoji} onChange={(event) => setEditing({ ...editing, emoji: event.target.value, tone: detectEmojiTone(event.target.value) })} maxLength={14} placeholder="😀" /><small>The closest theme color is selected automatically.</small></label>}</fieldset><fieldset className="theme-picker"><legend>Course background</legend><div>{subjectPalettes.map((palette) => <button type="button" className={editing.tone === palette.tone ? "selected" : ""} onClick={() => setEditing({ ...editing, tone: palette.tone })} key={palette.tone} aria-label={`Use ${palette.label} theme`}><i style={{ background: palette.color }}/><span>{palette.label}</span></button>)}</div></fieldset><label>Subject name<input autoFocus value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} maxLength={30} /></label><button type="submit" className="create-button"><Check /> Save changes</button></form></div>}
      {deleting && <div className="creator-backdrop" onMouseDown={() => setDeleting(null)}><section className="delete-modal" onMouseDown={(event) => event.stopPropagation()}><span><Trash2 /></span><span className="micro-label danger">DELETE SUBJECT</span><h2>Delete {deleting.name}?</h2><p>This removes the subject from your dashboard. Uploaded materials will also be removed when database storage is connected.</p><div><button onClick={() => setDeleting(null)}>Keep subject</button><button onClick={deleteSubject}><Trash2 /> Delete</button></div></section></div>}
      <AppMobileNav active="subjects" />
    </main>
  );
}
