import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import CollectionDetail from "./pages/CollectionDetail";
import DesignerDetail from "./pages/DesignerDetail";
import DesignerList from "./pages/DesignerList";
import NotFound from "./pages/NotFound";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter><Routes><Route element={<Layout />}>
      <Route path="/" element={<DesignerList />} />
      <Route path="/designers/:designerId" element={<DesignerDetail />} />
      <Route path="/collections/:collectionId" element={<CollectionDetail />} />
      <Route path="*" element={<NotFound />} />
    </Route></Routes></BrowserRouter>
  );
}
