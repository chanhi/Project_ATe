import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div style={{
      width: "200px",
      background: "#333",
      color: "white",
      height: "100vh",
      padding: "20px"
    }}>
      <div><Link to="/dashboard">Dashboard</Link></div>
      <div><Link to="/test-create">Test Create</Link></div>
    </div>
  );
}