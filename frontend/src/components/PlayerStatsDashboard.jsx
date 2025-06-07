import React, { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import axios from "axios";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";

export default function PlayerStatsDashboard() {
  const [players, setPlayers] = useState([]);
  const [selectedPlayer, setSelectedPlayer] = useState("2544"); // LeBron James as default
  const [seasons, setSeasons] = useState(["2023", "2022", "2021"]);
  const [selectedSeason, setSelectedSeason] = useState("2023");
  const [stats, setStats] = useState([]);

  useEffect(() => {
    const fetchPlayers = async () => {
      const res = await axios.get("http://localhost:8000/players");
      setPlayers(res.data);
    };
    fetchPlayers();
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      const res = await axios.get(`http://localhost:8000/player_stats?player_id=${selectedPlayer}&season=${selectedSeason}`);
      setStats(res.data);
    };
    fetchStats();
  }, [selectedPlayer, selectedSeason]);

  const handlePlayerChange = (e) => setSelectedPlayer(e.target.value);
  const handleSeasonChange = (e) => setSelectedSeason(e.target.value);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">NBA Player Stats Dashboard</h1>

      <div className="flex gap-4 mb-6">
        <Select onChange={handlePlayerChange} value={selectedPlayer}>
          {players.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </Select>
        <Select onChange={handleSeasonChange} value={selectedSeason}>
          {seasons.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>

      <Card>
        <CardContent>
          <Plot
            data={[{
              x: stats.map((g) => g.game_date),
              y: stats.map((g) => g.points),
              type: "scatter",
              mode: "lines+markers",
              marker: { color: "#3b82f6" },
            }]}
            layout={{
              title: "Points Per Game",
              xaxis: { title: "Game Date" },
              yaxis: { title: "Points" },
              autosize: true,
            }}
            style={{ width: "100%", height: "500px" }}
          />
        </CardContent>
      </Card>
    </div>
  );
}
