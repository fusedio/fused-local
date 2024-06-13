import { createRoot } from "react-dom/client";
import App from "./map";

const Index = () => {
    return <App />;
};

createRoot(document.getElementById("app") as HTMLElement).render(<Index />);
