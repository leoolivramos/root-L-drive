import { useEffect, useMemo, useState } from "react";
import { FaCircleNodes, FaComputer, FaFolderOpen, FaServer, FaUsb, FaSquarePlus, FaTrash, FaFolder, FaFile, FaChevronRight, FaDownload } from "react-icons/fa6";

import { listMachines, createMachine, revokeMachine, sendMachineCommand } from "../../api/machines";

export default function MachinesPage() {
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [createdToken, setCreatedToken] = useState(null);
  const [createdInstaller, setCreatedInstaller] = useState(null);
  const [status, setStatus] = useState("");

  // Browser modal state
  const [browsingMachine, setBrowsingMachine] = useState(null);
  const [currentPath, setCurrentPath] = useState("");
  const [items, setItems] = useState([]);
  const [pathHistory, setPathHistory] = useState([]);
  const [isBrowsingLoading, setIsBrowsingLoading] = useState(false);

  const browsingMachineInfo = useMemo(
    () => machines.find((machine) => machine.id === browsingMachine) || null,
    [machines, browsingMachine],
  );

  const joinRemotePath = (basePath, childName) => {
    if (!basePath) return childName;
    if (basePath.endsWith("\\") || basePath.endsWith("/")) return `${basePath}${childName}`;
    return `${basePath}\\${childName}`;
  };

  const base64ToBlob = (base64, mimeType = "application/octet-stream") => {
    const binaryString = window.atob(base64);
    const length = binaryString.length;
    const bytes = new Uint8Array(length);
    for (let index = 0; index < length; index += 1) {
      bytes[index] = binaryString.charCodeAt(index);
    }
    return new Blob([bytes], { type: mimeType });
  };

  const downloadBlob = (blob, filename) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const load = async () => {
    try {
      setLoading(true);
      const data = await listMachines();
      setMachines(data || []);
    } catch (err) {
      setStatus("Falha ao carregar maquinas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return setStatus("Informe um nome");
    try {
      const payload = { name: name.trim() };
      const res = await createMachine(payload);
      setCreatedToken(res.token);
      setCreatedInstaller(res.installer_script || null);
      setName("");
      await load();
    } catch (err) {
      setStatus("Erro ao criar maquina");
    }
  };

  const handleRevoke = async (id) => {
    try {
      await revokeMachine(id);
      await load();
    } catch {
      setStatus("Erro ao revogar");
    }
  };

  const openBrowser = async (machineId, initialPath = ".") => {
    setBrowsingMachine(machineId);
    setPathHistory([]);
    await loadDirectoryItems(machineId, initialPath);
  };

  const loadDirectoryItems = async (machineId, path) => {
    setIsBrowsingLoading(true);
    try {
      const resp = await sendMachineCommand(machineId, { cmd: "list", path });
      if (resp.ok && resp.result) {
        setCurrentPath(resp.result.path || path);
        setItems(resp.result.items || []);
        setPathHistory((prev) => [...prev, resp.result.path || path]);
      } else {
        setStatus(`Erro ao listar: ${resp.error}`);
      }
    } catch (e) {
      setStatus("Falha ao carregar diretório");
    } finally {
      setIsBrowsingLoading(false);
    }
  };

  const handleOpenFolder = (itemName) => {
    const nextPath = joinRemotePath(currentPath, itemName);
    loadDirectoryItems(browsingMachine, nextPath);
  };

  const handleDownloadFile = async (itemName) => {
    try {
      const path = joinRemotePath(currentPath, itemName);
      setIsBrowsingLoading(true);
      const resp = await sendMachineCommand(browsingMachine, {
        cmd: "read",
        path,
        max_bytes: 50 * 1024 * 1024,
      });

      if (resp.ok && resp.result?.data_b64) {
        const blob = base64ToBlob(resp.result.data_b64);
        downloadBlob(blob, itemName);
        setStatus(`Download iniciado: ${itemName}`);
      } else {
        setStatus(`Erro ao baixar: ${resp.error || "resposta inválida"}`);
      }
    } catch (e) {
      setStatus("Falha ao baixar arquivo");
    } finally {
      setIsBrowsingLoading(false);
    }
  };

  const handleGoBack = () => {
    if (pathHistory.length > 1) {
      const newHistory = pathHistory.slice(0, -1);
      setPathHistory(newHistory);
      const prevPath = newHistory[newHistory.length - 1];
      loadDirectoryItems(browsingMachine, prevPath);
    }
  };

  const closeBrowser = () => {
    setBrowsingMachine(null);
    setCurrentPath("");
    setItems([]);
    setPathHistory([]);
  };

  const handleList = async (id) => {
    openBrowser(id, ".");
  };

  return (
    <section className="page-block">
      <header className="page-header card proto-hero">
        <div>
          <p className="eyebrow">Integrações</p>
          <h2>Máquinas</h2>
          <p className="muted">Gerencie acessos nas máquinas e autorize diretórios.</p>
        </div>
      </header>

      {status && <p className="status">{status}</p>}

      <section className="proto-split machines-layout">
        <article className="card proto-panel proto-machine-shell">
          <div className="action-head">
            <h3>Nova máquina</h3>
          </div>

          <div className="proto-form">
            <label className="proto-field">
              Nome
              <input className="proto-input" value={name} onChange={(e) => setName(e.target.value)} />
            </label>

            <p className="muted">Os diretórios autorizados são definidos ao executar o script instalado.</p>

            <div className="row-actions">
              <button className="primary" onClick={handleCreate}>
                <FaSquarePlus aria-hidden="true" /> Criar máquina
              </button>
            </div>

            {createdToken && (
              <div className="proto-secret-box">
                <div>
                  <p className="eyebrow">Token exibido apenas uma vez</p>
                  <code>{createdToken}</code>
                </div>
                {createdInstaller ? (
                  <div style={{ marginLeft: 12 }}>
                    <a
                      href={URL.createObjectURL(new Blob([createdInstaller], { type: "text/x-python" }))}
                      download={`install_${Date.now()}.py`}
                      className="primary"
                    >
                      Baixar script
                    </a>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </article>

        <article className="card proto-panel">
          <div className="action-head">
            <h3>Máquinas registradas</h3>
            <span className="muted">{machines.length} registros</span>
          </div>

          {loading ? (
            <p className="muted">Carregando...</p>
          ) : (
            <ul className="proto-key-list">
              {machines.length === 0 && <li className="muted">Nenhuma máquina registrada.</li>}
              {machines.map((m) => (
                <li key={m.id} className="proto-key-item">
                  <div className="proto-key-main">
                    <div className="proto-machine-icon">
                      <FaComputer aria-hidden="true" />
                    </div>
                    <div>
                      <strong>{m.name}</strong>
                      <p className="muted">Pastas: {m.allowed_paths?.join(", ")}</p>
                    </div>
                  </div>

                  <div className="proto-key-meta">
                    <span className={`status-pill ${m.is_active ? "active" : "inactive"}`}>{m.is_active ? "Ativa" : "Revogada"}</span>
                  </div>

                  <div className="row-actions">
                    <button className="ghost" onClick={() => handleList(m.id)}>Listar</button>
                    <button className="danger"
                      onClick={() => handleRevoke(m.id)}
                      disabled={!m.is_active}
                    >
                      <FaTrash /> Revogar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>

      {/* File Browser Modal */}
      {browsingMachine && (
        <div style={{
          position: "fixed",
          inset: 0,
          backgroundColor: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 999,
        }}>
          <div className="card" style={{
            width: "90%",
            maxWidth: "700px",
            maxHeight: "80vh",
            display: "flex",
            flexDirection: "column",
            padding: 0,
          }}>
            <div style={{ padding: "20px", borderBottom: "1px solid var(--color-border)" }}>
              <h3>{browsingMachineInfo?.name || "Navegador"}</h3>
              <p className="muted" style={{ fontSize: "0.9em", marginTop: "8px" }}>{currentPath}</p>
            </div>

            <div style={{
              flex: 1,
              overflowY: "auto",
              padding: "20px",
            }}>
              {isBrowsingLoading ? (
                <p className="muted">Carregando...</p>
              ) : items.length === 0 ? (
                <p className="muted">Diretório vazio</p>
              ) : (
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {items.map((item, idx) => {
                    const isDir = !item.includes(".");
                    return (
                      <li
                        key={idx}
                        style={{
                          padding: "12px",
                          marginBottom: "8px",
                          backgroundColor: "var(--color-bg-alt)",
                          borderRadius: "4px",
                          display: "flex",
                          alignItems: "center",
                          cursor: isDir ? "pointer" : "default",
                          transition: "background-color 0.2s",
                        }}
                        onMouseEnter={(e) => isDir && (e.currentTarget.style.backgroundColor = "var(--color-primary-faint)")}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "var(--color-bg-alt)")}
                        onClick={() => isDir && handleOpenFolder(item)}
                      >
                        {isDir ? (
                          <FaFolder style={{ marginRight: "12px", color: "var(--color-primary)" }} />
                        ) : (
                          <FaFile style={{ marginRight: "12px", color: "var(--color-muted)" }} />
                        )}
                        <span style={{ flex: 1 }}>{item}</span>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          {!isDir && (
                            <button
                              className="ghost"
                              onClick={(event) => {
                                event.stopPropagation();
                                handleDownloadFile(item);
                              }}
                            >
                              <FaDownload aria-hidden="true" /> Baixar
                            </button>
                          )}
                          {isDir && <FaChevronRight style={{ color: "var(--color-muted)", fontSize: "0.8em" }} />}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div style={{
              padding: "20px",
              borderTop: "1px solid var(--color-border)",
              display: "flex",
              gap: "12px",
              justifyContent: "flex-end",
            }}>
              {pathHistory.length > 1 && (
                <button className="ghost" onClick={handleGoBack}>Voltar</button>
              )}
              <button className="ghost" onClick={closeBrowser}>Fechar</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}