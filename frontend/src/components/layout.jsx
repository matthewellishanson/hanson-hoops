import React from "react";

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow p-4">
        <h1 className="text-xl font-bold">🏀 NBA Data Blog</h1>
      </header>

      <main className="p-6 max-w-6xl mx-auto">
        {children}
      </main>

      <footer className="text-center text-gray-500 text-sm p-4 mt-10">
        © {new Date().getFullYear()} NBA Dashboard Blog
      </footer>
    </div>
  );
}
