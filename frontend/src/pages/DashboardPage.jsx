import React from "react";
import PlayerStatsDashboard from "@/components/PlayerStatsDashboard";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Site header / nav could go here */}
      <header className="bg-white shadow p-4 mb-6">
        <h1 className="text-2xl font-semibold text-center">🏀 NBA Data Blog</h1>
      </header>

      <main>
        <PlayerStatsDashboard />
      </main>

      {/* Optional footer */}
      <footer className="text-center text-sm text-gray-400 py-4">
        © {new Date().getFullYear()} NBA Blog Dashboard
      </footer>
    </div>
  );
}
