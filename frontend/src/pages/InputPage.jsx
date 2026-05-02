import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { executeTest } from "../api/testApi";

export default function InputPage() {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const navigate = useNavigate();
  const [url, setUrl] = useState("");

  const handleSubmit = async () => {
    if (!url) {
      alert("URL을 입력하거나 대표 사이트를 선택해주세요.");
      return;
    }

    try {
      console.log("자연어 입력:", text);
      console.log("첨부파일:", file);

      const result = await executeTest({ url });
      const testRunId = result.data.test_run_id;

      navigate(`/test-run?testRunId=${testRunId}`);
    } catch (error) {
      console.error(error);
      alert("테스트 실행 요청에 실패했습니다.");
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      {/* 상단 배너 */}
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

      {/* 자연어 입력 */}
      <div style={{ marginTop: "20px" }}>
        <h3>직접 작성</h3>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{
            width: "100%",
            height: "120px",
            padding: "10px",
            border: "2px solid black",
            boxSizing: "border-box"
          }}
        />
      </div>

      {/* 파일 업로드 */}
      <div style={{ marginTop: "20px" }}>
  <h3>첨부파일</h3>

  <div
    style={{
      border: "2px solid black",
      height: "120px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxSizing: "border-box"
    }}
  >
    <input type="file" onChange={(e) => setFile(e.target.files[0])} />
  </div>
</div>

{/* URL 입력 */}
<div style={{ marginTop: "30px" }}>
  <h3>URL 입력</h3>
  <input
    value={url}
    onChange={(e) => setUrl(e.target.value)}
    placeholder="https://example.com"
    style={{
      width: "100%",
      padding: "10px",
      border: "2px solid black",
      boxSizing: "border-box",
    }}
  />
</div>

{/* 대표 사이트 선택 */}
<div
  style={{
    marginTop: "10px",
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: "8px",
  }}
>
  <label>
    <input
      type="radio"
      name="site"
      onChange={() => setUrl("https://google.com")}
    />
    https://google.com
  </label>

  <label>
    <input
      type="radio"
      name="site"
      onChange={() => setUrl("https://naver.com")}
    />
    https://naver.com
  </label>

  <label>
    <input
      type="radio"
      name="site"
      onChange={() => setUrl("https://github.com")}
    />
    https://github.com
  </label>
</div>

      {/* 버튼 */}
      <div style={{ 
        marginTop: "30px",
        display:  "flex",
        justifyContent: "flex-end"
       }}>
        <button onClick={handleSubmit}>
          확인
        </button>
      </div>
    </div>
  );
}