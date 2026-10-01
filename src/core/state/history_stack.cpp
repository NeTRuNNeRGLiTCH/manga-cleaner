#include "history_stack.h"
#include "src/diagnostics/logger.h"

history_stack::history_stack(int max_history_size) : m_max_size(max_history_size) {
    LOG_TRACE(QString("History Stack initialized (Capacity: %1)").arg(m_max_size));
}

history_stack::~history_stack() {
    clear();
}

void history_stack::clear() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_undo_stack.clear();
    m_redo_stack.clear();
    LOG_TRACE("History Stack cleared.");
}

void history_stack::commit_image_patch(const cv::Rect& roi, const cv::Mat& before, const cv::Mat& after) {
    if (before.empty() || after.empty()) return;

    try {
        std::lock_guard<std::mutex> lock(m_mutex);
        HistoryAction action;
        action.type = ActionType::ImagePatch;
        action.roi = roi;
        action.old_pixels = before.clone();
        action.new_pixels = after.clone();

        m_undo_stack.push_back(std::move(action));
        if (m_undo_stack.size() > static_cast<size_t>(m_max_size)) {
            m_undo_stack.pop_front();
        }
        m_redo_stack.clear();

        LOG_TRACE("Image patch delta recorded in History Stack.");
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in commit_image_patch: ") + e.what());
    }
}

void history_stack::commit_mask_state(const cv::Mat& before, const cv::Mat& after) {
    try {
        std::lock_guard<std::mutex> lock(m_mutex);
        HistoryAction action;
        action.type = ActionType::MaskState;
        action.old_mask = before.empty() ? cv::Mat() : before.clone();
        action.new_mask = after.empty() ? cv::Mat() : after.clone();

        m_undo_stack.push_back(std::move(action));
        if (m_undo_stack.size() > static_cast<size_t>(m_max_size)) {
            m_undo_stack.pop_front();
        }
        m_redo_stack.clear();

        LOG_TRACE("Mask state delta recorded in History Stack.");
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in commit_mask_state: ") + e.what());
    }
}

bool history_stack::undo_selection(session_data* current_session) {
    if (!current_session) return false;

    std::lock_guard<std::mutex> lock(m_mutex);
    for (auto it = m_undo_stack.rbegin(); it != m_undo_stack.rend(); ++it) {
        if (it->type == ActionType::MaskState) {
            HistoryAction action = std::move(*it);
            m_undo_stack.erase(std::next(it).base());
            current_session->set_mask(action.old_mask);
            LOG_INFO("Undo executed: Selection / Mask reverted.");
            m_redo_stack.push_back(std::move(action));
            return true;
        }
    }
    return false;
}

bool history_stack::redo_selection(session_data* current_session) {
    if (!current_session) return false;

    std::lock_guard<std::mutex> lock(m_mutex);
    for (auto it = m_redo_stack.rbegin(); it != m_redo_stack.rend(); ++it) {
        if (it->type == ActionType::MaskState) {
            HistoryAction action = std::move(*it);
            m_redo_stack.erase(std::next(it).base());
            current_session->set_mask(action.new_mask);
            LOG_INFO("Redo executed: Selection / Mask reapplied.");
            m_undo_stack.push_back(std::move(action));
            return true;
        }
    }
    return false;
}

bool history_stack::undo_inpaint(session_data* current_session) {
    if (!current_session) return false;

    std::lock_guard<std::mutex> lock(m_mutex);
    for (auto it = m_undo_stack.rbegin(); it != m_undo_stack.rend(); ++it) {
        if (it->type == ActionType::ImagePatch) {
            HistoryAction action = std::move(*it);
            m_undo_stack.erase(std::next(it).base());
            current_session->apply_cleaned_patch(action.roi, action.old_pixels);
            LOG_INFO("Undo executed: Inpaint patch reverted.");
            m_redo_stack.push_back(std::move(action));
            return true;
        }
    }
    return false;
}

bool history_stack::redo_inpaint(session_data* current_session) {
    if (!current_session) return false;

    std::lock_guard<std::mutex> lock(m_mutex);
    for (auto it = m_redo_stack.rbegin(); it != m_redo_stack.rend(); ++it) {
        if (it->type == ActionType::ImagePatch) {
            HistoryAction action = std::move(*it);
            m_redo_stack.erase(std::next(it).base());
            current_session->apply_cleaned_patch(action.roi, action.new_pixels);
            LOG_INFO("Redo executed: Inpaint patch reapplied.");
            m_undo_stack.push_back(std::move(action));
            return true;
        }
    }
    return false;
}