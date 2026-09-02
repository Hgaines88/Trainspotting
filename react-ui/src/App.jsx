import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAdmin from "./components/RequireAdmin";
import RequireAuthenticated from "./components/RequireAuthenticated";
import RequireModerator from "./components/RequireModerator";
import CollectionDetail from "./pages/CollectionDetail";
import CollectionForm from "./pages/CollectionForm";
import DesignerDetail from "./pages/DesignerDetail";
import DesignerForm from "./pages/DesignerForm";
import DesignerList from "./pages/DesignerList";
import NotFound from "./pages/NotFound";
import SubmissionForm from "./pages/SubmissionForm";
import MySubmissions from "./pages/MySubmissions";
import ModerationQueue from "./pages/ModerationQueue";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter><Routes><Route element={<Layout />}>
      <Route path="/" element={<DesignerList />} />
      <Route path="/designers/:designerId" element={<DesignerDetail />} />
      <Route path="/collections/:collectionId" element={<CollectionDetail />} />
      <Route path="/designers/new" element={<RequireAdmin><DesignerForm /></RequireAdmin>} />
      <Route path="/designers/:designerId/edit" element={<RequireAdmin><DesignerForm /></RequireAdmin>} />
      <Route path="/designers/:designerId/collections/new" element={<RequireAdmin><CollectionForm /></RequireAdmin>} />
      <Route path="/collections/:collectionId/edit" element={<RequireAdmin><CollectionForm /></RequireAdmin>} />
      <Route path="/submissions/new" element={<RequireAuthenticated><SubmissionForm /></RequireAuthenticated>} />
      <Route path="/submissions/mine" element={<RequireAuthenticated><MySubmissions /></RequireAuthenticated>} />
      <Route path="/moderation" element={<RequireModerator><ModerationQueue /></RequireModerator>} />
      <Route path="*" element={<NotFound />} />
    </Route></Routes></BrowserRouter>
  );
}
