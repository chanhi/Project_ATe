export default function TestRunPage() {
  return (
    <div style={{ padding: "20px" }}>
      <h1
        style={{
          borderBottom: "2px solid black",
          paddingBottom: "10px",
          textAlign: "left",
          paddingLeft: "20px",
        }}
      >
        ATe
      </h1>

      <div style={{ marginTop: "30px" }}>
        <h3>테스트 결과</h3>

        <div
          style={{
            border: "2px solid black",
            height: "300px",
            padding: "10px",
            boxSizing: "border-box",
          }}
        >
          결과 출력 영역
        </div>
      </div>
    </div>
  );
}