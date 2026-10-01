#ifndef CORE_STATE_HISTORY_STACK_H
#define CORE_STATE_HISTORY_STACK_H

#include "session_data.h"
#include <opencv2/opencv.hpp>
#include <deque>
#include <mutex>

enum class ActionType {
    ImagePatch, // AI or manual inpaint modified an ROI
    MaskState   // User drew, erased, or detected a mask
};

struct HistoryAction {
    ActionType type;
    cv::Rect roi;
    cv::Mat old_pixels;
    cv::Mat new_pixels;
    cv::Mat old_mask;
    cv::Mat new_mask;
};

class history_stack {
public:
    explicit history_stack(int max_history_size = 20);
    ~history_stack();

    void commit_image_patch(const cv::Rect& roi, const cv::Mat& before, const cv::Mat& after);
    void commit_mask_state(const cv::Mat& before, const cv::Mat& after);

    // Targeted Undo & Redo
    bool undo_selection(session_data* current_session);
    bool redo_selection(session_data* current_session);
    bool undo_inpaint(session_data* current_session);
    bool redo_inpaint(session_data* current_session);

    void clear();

private:
    mutable std::mutex m_mutex;
    int m_max_size;
    std::deque<HistoryAction> m_undo_stack;
    std::deque<HistoryAction> m_redo_stack;
};

#endif // CORE_STATE_HISTORY_STACK_H