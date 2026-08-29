import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const TRACKS = [
  { id: "", label: "Overall" },
  { id: "sde", label: "SDE" },
  { id: "pm", label: "PM" },
  { id: "data_science", label: "Data Science" },
  { id: "upsc", label: "UPSC" },
];

function Board({ board }: { board: any }) {
  if (!board) return <p className="text-gray-400 text-sm">Loading…</p>;
  if (!board.entries?.length)
    return (
      <p className="text-gray-500 text-sm">
        No entries yet — take an interview to get on the board!
      </p>
    );
  return (
    <div className="space-y-1">
      {board.entries.map((e: any) => (
        <div
          key={e.rank}
          className={`flex items-center justify-between px-3 py-2 rounded-lg ${
            e.is_me ? "bg-brand-600/25 border border-brand-500/40" : "bg-white/5"
          }`}
        >
          <div className="flex items-center gap-3">
            <span
              className={`w-7 text-center font-bold ${
                e.rank === 1
                  ? "text-yellow-400"
                  : e.rank === 2
                  ? "text-gray-300"
                  : e.rank === 3
                  ? "text-amber-600"
                  : "text-gray-500"
              }`}
            >
              {e.rank <= 3 ? ["🥇", "🥈", "🥉"][e.rank - 1] : e.rank}
            </span>
            <span className="font-medium">
              {e.username}
              {e.is_me && <span className="text-xs text-brand-300"> (you)</span>}
            </span>
          </div>
          <div className="text-right">
            <span className="font-bold text-brand-300">{e.best_score}</span>
            <span className="text-xs text-gray-500"> · {e.interviews} done</span>
          </div>
        </div>
      ))}
      {board.my_rank && board.my_rank > board.entries.length && (
        <div className="mt-2 text-xs text-gray-400 text-center">
          Your rank: #{board.my_rank}
        </div>
      )}
    </div>
  );
}

export default function Leaderboard() {
  const nav = useNavigate();
  const [track, setTrack] = useState("");
  const [board, setBoard] = useState<any>(null);
  const [challenge, setChallenge] = useState<any>(null);

  useEffect(() => {
    api.leaderboard(track || undefined).then(setBoard).catch(() => {});
  }, [track]);

  useEffect(() => {
    api.challenge().then(setChallenge).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Leaderboard 🏆</h1>

      {/* Weekly challenge */}
      {challenge?.challenge && (
        <div className="rounded-2xl bg-gradient-to-br from-brand-600/30 to-white/5 border border-brand-500/30 p-5">
          <div className="text-xs uppercase text-brand-300">
            This week's challenge
          </div>
          <div className="text-xl font-bold mt-1">
            {challenge.challenge.title}
          </div>
          <p className="text-sm text-gray-300 mt-1">
            {challenge.challenge.prompt}
          </p>
          <button
            onClick={() => nav("/interview")}
            className="mt-3 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-sm"
          >
            Take the challenge →
          </button>
          <div className="mt-4">
            <div className="text-xs uppercase text-gray-400 mb-2">
              Challenge ranking (this week)
            </div>
            <Board board={challenge} />
          </div>
        </div>
      )}

      {/* Global / per-track */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="flex flex-wrap gap-2 mb-4">
          {TRACKS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTrack(t.id)}
              className={`px-3 py-1.5 rounded-lg text-sm ${
                track === t.id ? "bg-brand-600" : "bg-white/10 hover:bg-white/20"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Board board={board} />
      </div>
    </div>
  );
}
